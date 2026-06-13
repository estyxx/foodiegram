import logging
import re
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from foodiegram.api_models import (
    RecipeDetail,
    RecipeSummary,
    RecipeUpdate,
    ScaledIngredient,
    ScaleResult,
)
from foodiegram.domain.enums import CuisineType, Difficulty, DishType, MealType
from foodiegram.domain.errors import StorageError
from foodiegram.repository import RecipeRepository
from foodiegram.settings import Settings

logger = logging.getLogger(__name__)

_settings = Settings()
_repo = RecipeRepository(_settings.data_dir)

app = FastAPI(title="Foodiegram API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_NUMBER_RE = re.compile(r"\d+\.?\d*")


def _scale_text(raw: str, factor: float) -> str:
    """Replace every number in raw with its value multiplied by factor, 2 dp."""

    def _replace(m: re.Match[str]) -> str:
        return str(round(float(m.group()) * factor, 2))

    return _NUMBER_RE.sub(_replace, raw)


def _first_number(text: str) -> float | None:
    """Return the first numeric value in text, or None."""
    m = _NUMBER_RE.search(text)
    return float(m.group()) if m else None


def _to_enum[T](cls: type[T], value: str) -> T | None:
    """Coerce value to cls; return None if the value is not a valid member."""
    try:
        return cls(value.lower())  # type: ignore[call-arg]  # reason: StrEnum callable
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/recipes")
async def list_recipes(
    cuisine: Annotated[str | None, Query()] = None,
    meal_type: Annotated[str | None, Query()] = None,
    dish_type: Annotated[str | None, Query()] = None,
    difficulty: Annotated[str | None, Query()] = None,
    dietary_tag: Annotated[str | None, Query()] = None,
    protein: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    is_favorite: Annotated[bool | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[RecipeSummary]:
    """Return a filtered, paginated list of recipe summaries."""
    recipes = _repo.find(
        cuisine=_to_enum(CuisineType, cuisine) if cuisine else None,
        meal_type=_to_enum(MealType, meal_type) if meal_type else None,
        dish_type=_to_enum(DishType, dish_type) if dish_type else None,
        difficulty=_to_enum(Difficulty, difficulty) if difficulty else None,
        dietary_tags=[dietary_tag] if dietary_tag else None,
        proteins=[protein] if protein else None,
        q=q,
        is_favorite=is_favorite,
    )
    page = recipes[offset : offset + limit]
    return [RecipeSummary.from_recipe(r) for r in page]


@app.get("/recipes/{code}")
async def get_recipe(code: str) -> RecipeDetail:
    """Return the full recipe for code, or 404."""
    recipe = _repo.get(code)
    if recipe is None:
        msg = f"Recipe {code!r} not found"
        raise HTTPException(status_code=404, detail=msg)
    return RecipeDetail.model_validate(recipe.model_dump())


@app.patch("/recipes/{code}")
async def update_recipe(code: str, body: RecipeUpdate) -> RecipeDetail:
    """Apply partial user edits to a recipe and persist them.

    Only user_notes, is_favorite, and base_servings are editable.
    Sets edited_by_user=True automatically.
    """
    recipe = _repo.get(code)
    if recipe is None:
        msg = f"Recipe {code!r} not found"
        raise HTTPException(status_code=404, detail=msg)

    changes: dict[str, Any] = {
        k: v for k, v in body.model_dump().items() if k in body.model_fields_set
    }
    changes["edited_by_user"] = True

    try:
        updated = RecipeDetail.model_validate({**recipe.model_dump(), **changes})
        _repo.save(updated)
    except StorageError as exc:
        logger.exception("Failed to save recipe %s", code)
        msg = f"Could not persist recipe {code!r}"
        raise HTTPException(status_code=500, detail=msg) from exc

    return updated


@app.get("/recipes/{code}/scale")
async def scale_recipe(
    code: str,
    servings: Annotated[float | None, Query()] = None,
    ingredient: Annotated[str | None, Query()] = None,
    amount: Annotated[float | None, Query()] = None,
) -> ScaleResult:
    """Scale recipe ingredients by target serving count or a reference ingredient."""
    recipe = _repo.get(code)
    if recipe is None:
        msg = f"Recipe {code!r} not found"
        raise HTTPException(status_code=404, detail=msg)

    # --- Determine scaling factor ---
    factor: float
    scaled_servings: float | None

    if servings is not None:
        if recipe.base_servings is None:
            msg = "Recipe has no base_servings; cannot scale by servings"
            raise HTTPException(status_code=422, detail=msg)
        factor = servings / recipe.base_servings
        scaled_servings = servings

    elif ingredient is not None and amount is not None:
        needle = ingredient.lower()
        match = next(
            (ing for ing in recipe.ingredients if needle in ing.lower()),
            None,
        )
        if match is None:
            msg = f"No ingredient matching {ingredient!r} found"
            raise HTTPException(status_code=422, detail=msg)
        qty = _first_number(match)
        if qty is None:
            msg = f"Could not extract a quantity from {match!r}"
            raise HTTPException(status_code=422, detail=msg)
        factor = amount / qty
        scaled_servings = (
            recipe.base_servings * factor if recipe.base_servings is not None else None
        )

    else:
        msg = "Provide either 'servings' or both 'ingredient' and 'amount'"
        raise HTTPException(status_code=422, detail=msg)

    # --- Apply factor to every ingredient ---
    scaled = [
        ScaledIngredient(
            raw_text=ing,
            scaled_text=_scale_text(ing, factor),
            factor=round(factor, 4),
        )
        for ing in recipe.ingredients
    ]

    return ScaleResult(
        code=code,
        factor=round(factor, 4),
        base_servings=recipe.base_servings,
        scaled_servings=(
            round(scaled_servings, 2) if scaled_servings is not None else None
        ),
        ingredients=scaled,
    )


# Static files — must come after all API routes so the mount does not shadow them.
_PUBLIC = Path(__file__).parent.parent.parent / "public"


@app.get("/")
async def serve_index() -> FileResponse:
    """Serve the frontend SPA."""
    return FileResponse(_PUBLIC / "index.html")


app.mount("/", StaticFiles(directory=_PUBLIC), name="static")


def main() -> None:
    """Start the API server using host/port from Settings."""
    uvicorn.run(
        "foodiegram.api:app",
        host=_settings.api_host,
        port=_settings.api_port,
        reload=False,
    )
