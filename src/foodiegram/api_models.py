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
    def from_recipe(cls, recipe: Recipe) -> "RecipeSummary":
        """Build a RecipeSummary from a Recipe."""
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
            is_favorite=recipe.is_favorite,
            has_instructions=bool(recipe.instructions),
        )


class RecipeDetail(Recipe):
    """Full recipe response for single-recipe API endpoints."""


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
