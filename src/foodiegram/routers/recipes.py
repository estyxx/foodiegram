import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from foodiegram.api_models import (
    RecipeDetail,
    RecipeSummary,
    RecipeUpdate,
    ScaledIngredient,
    ScaleResult,
)
from foodiegram.deps import DepsDep
from foodiegram.domain.enums import CuisineType, Difficulty, DishType, MealType
from foodiegram.domain.errors import StorageError
from foodiegram.domain.models import Recipe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

_NUMBER_RE = re.compile(r"\d+\.?\d*")


def _scale_text(raw: str, factor: float) -> str:
    """Replace every number in raw with its value multiplied by factor, 2 dp."""

    def _replace(match: re.Match[str]) -> str:
        return str(round(float(match.group()) * factor, 2))

    return _NUMBER_RE.sub(_replace, raw)


def _first_number(text: str) -> float | None:
    """Return the first numeric value in text, or None."""
    match = _NUMBER_RE.search(text)
    return float(match.group()) if match else None


def _to_enum[T](cls: type[T], value: str) -> T | None:
    """Coerce value to cls; return None if the value is not a valid member."""
    try:
        return cls(value.lower())  # type: ignore[call-arg]  # reason: StrEnum callable
    except ValueError:
        return None


def _detail(recipe: Recipe, *, deps: DepsDep) -> RecipeDetail:
    """Build a RecipeDetail, resolving favourite/notes from user_state."""
    state = deps.user_state.get(recipe.code)
    return RecipeDetail.model_validate(
        {
            **recipe.model_dump(),
            "is_favorite": state.is_favorite if state else False,
            "user_notes": state.user_notes if state else None,
        },
    )


@router.get("/recipes")
async def list_recipes(
    deps: DepsDep,
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
    recipes = deps.recipes.find(
        cuisine=_to_enum(CuisineType, cuisine) if cuisine else None,
        meal_type=_to_enum(MealType, meal_type) if meal_type else None,
        dish_type=_to_enum(DishType, dish_type) if dish_type else None,
        difficulty=_to_enum(Difficulty, difficulty) if difficulty else None,
        dietary_tags=[dietary_tag] if dietary_tag else None,
        proteins=[protein] if protein else None,
        q=q,
    )
    favourites = set(deps.user_state.all_favorites())
    if is_favorite is not None:
        recipes = [r for r in recipes if (r.code in favourites) == is_favorite]
    page = recipes[offset : offset + limit]
    return [
        RecipeSummary.from_recipe(recipe, is_favorite=recipe.code in favourites)
        for recipe in page
    ]


@router.get("/recipes/{code}")
async def get_recipe(code: str, deps: DepsDep) -> RecipeDetail:
    """Return the full recipe for code, or 404."""
    recipe = deps.recipes.get(code)
    if recipe is None:
        msg = f"Recipe {code!r} not found"
        raise HTTPException(status_code=404, detail=msg)
    return _detail(recipe, deps=deps)


@router.patch("/recipes/{code}")
async def update_recipe(code: str, body: RecipeUpdate, deps: DepsDep) -> RecipeDetail:
    """Apply partial user edits: recipe fields to the recipe, app state to user_state.

    base_servings maps to a Recipe field (sets edited_by_user); is_favorite and
    user_notes are per-user app state and are written to user_state instead.
    """
    recipe = deps.recipes.get(code)
    if recipe is None:
        msg = f"Recipe {code!r} not found"
        raise HTTPException(status_code=404, detail=msg)

    recipe_changes: dict[str, Any] = {
        key: value
        for key, value in body.model_dump().items()
        if key in body.model_fields_set and key in Recipe.model_fields
    }
    if recipe_changes:
        recipe_changes["edited_by_user"] = True
        recipe = recipe.model_copy(update=recipe_changes)
        try:
            deps.recipes.save(recipe)
        except StorageError as exc:
            logger.exception("Failed to save recipe %s", code)
            msg = f"Could not persist recipe {code!r}"
            raise HTTPException(status_code=500, detail=msg) from exc

    if "is_favorite" in body.model_fields_set and body.is_favorite is not None:
        deps.user_state.set_favorite(code, is_favorite=body.is_favorite)
    if "user_notes" in body.model_fields_set:
        deps.user_state.set_notes(code, notes=body.user_notes)

    return _detail(recipe, deps=deps)


@router.get("/recipes/{code}/scale")
async def scale_recipe(
    code: str,
    deps: DepsDep,
    servings: Annotated[float | None, Query()] = None,
    ingredient: Annotated[str | None, Query()] = None,
    amount: Annotated[float | None, Query()] = None,
) -> ScaleResult:
    """Scale recipe ingredients by target serving count or a reference ingredient."""
    recipe = deps.recipes.get(code)
    if recipe is None:
        msg = f"Recipe {code!r} not found"
        raise HTTPException(status_code=404, detail=msg)

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
