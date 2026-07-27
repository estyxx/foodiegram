from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from foodiegram.domain.models import Recipe


class RecipeSummary(BaseModel):
    """Lightweight recipe representation for list views."""

    model_config = ConfigDict(frozen=True)

    code: str
    title: str
    cuisine_type: str
    meal_type: str
    dish_type: str
    difficulty: str
    dietary_tags: list[str]
    proteins: list[str]
    thumbnail_url: str | None
    cloudinary_url: str | None
    is_favorite: bool
    has_instructions: bool

    @classmethod
    def from_recipe(cls, recipe: Recipe, *, is_favorite: bool = False) -> RecipeSummary:
        """Build a RecipeSummary from a Recipe, with favourite state applied."""
        return cls(
            code=recipe.code,
            title=recipe.title,
            cuisine_type=recipe.cuisine_type,
            meal_type=recipe.meal_type,
            dish_type=recipe.dish_type,
            difficulty=recipe.difficulty,
            dietary_tags=recipe.dietary_tags,
            proteins=recipe.proteins,
            thumbnail_url=recipe.thumbnail_url,
            cloudinary_url=recipe.cloudinary_url,
            is_favorite=is_favorite,
            has_instructions=bool(recipe.instructions),
        )


class RecipeDetail(Recipe):
    """Full recipe response for single-recipe API endpoints.

    Carries per-user app state (favourite, notes) resolved from user_state at
    the API boundary; the domain Recipe stays free of app state.
    """

    is_favorite: bool = False
    user_notes: str | None = None


class ScaledIngredient(BaseModel):
    """One ingredient with its original and scaled text."""

    model_config = ConfigDict(frozen=True)

    raw_text: str
    scaled_text: str
    factor: float


class ScaleResult(BaseModel):
    """Response for the /recipes/{code}/scale endpoint."""

    model_config = ConfigDict(frozen=True)

    code: str
    factor: float
    base_servings: int | None
    scaled_servings: float | None
    ingredients: list[ScaledIngredient]


class RecipeUpdate(BaseModel):
    """PATCH body for /recipes/{code}. Only provided fields are applied."""

    model_config = ConfigDict(extra="forbid")

    user_notes: str | None = None
    is_favorite: bool | None = None
    base_servings: int | None = None


class PlannedMealOut(BaseModel):
    """A meal slot in the plan response."""

    model_config = ConfigDict(frozen=True)

    id: int | None
    day: date
    meal: str
    recipe_code: str
    portions: int


class CategoryStatusOut(BaseModel):
    """One category's planned servings against its target, flattened for the FE."""

    model_config = ConfigDict(frozen=True)

    category: str
    planned: float
    min_servings: float
    max_servings: float
    state: str


class GapSuggestion(BaseModel):
    """Suggested recipes to fill one under-target category."""

    model_config = ConfigDict(frozen=True)

    category: str
    recipes: list[RecipeSummary]


class PlanResponse(BaseModel):
    """Plan + balance + suggestions in one payload; the FE does no balance math."""

    model_config = ConfigDict(frozen=True)

    week_start: date
    meals: list[PlannedMealOut]
    balance: list[CategoryStatusOut]
    oily_fish: float
    suggestions: list[GapSuggestion]


class MealUpsert(BaseModel):
    """PUT body for a meal slot; upsert is keyed by (day, meal)."""

    model_config = ConfigDict(extra="forbid")

    day: date
    meal: Literal["lunch", "dinner"]
    recipe_code: str
    portions: int = 2


class PantryItemOut(BaseModel):
    """A pantry item in API responses."""

    model_config = ConfigDict(frozen=True)

    id: int | None
    name: str
    kind: str
    expires: date | None


class PantryItemCreate(BaseModel):
    """POST body to add a pantry item."""

    model_config = ConfigDict(extra="forbid")

    name: str
    kind: Literal["staple", "fresh"]
    expires: date | None = None


class TargetOut(BaseModel):
    """A weekly category target in API responses."""

    model_config = ConfigDict(frozen=True)

    category: str
    min_servings: float
    max_servings: float


class TargetIn(BaseModel):
    """One target inside a PUT /targets body."""

    model_config = ConfigDict(extra="forbid")

    category: str
    min_servings: float
    max_servings: float


class TargetsUpdate(BaseModel):
    """PUT body replacing the weekly targets."""

    model_config = ConfigDict(extra="forbid")

    targets: list[TargetIn]


class ShoppingItemOut(BaseModel):
    """A needed ingredient with the raw lines it came from."""

    model_config = ConfigDict(frozen=True)

    name: str
    raw_lines: list[str]


class AisleGroupOut(BaseModel):
    """Shopping items grouped by aisle."""

    model_config = ConfigDict(frozen=True)

    aisle: str
    items: list[ShoppingItemOut]
