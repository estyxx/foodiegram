import contextlib
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from foodiegram.domain.enums import CuisineType, Difficulty, DishType, MealType

if TYPE_CHECKING:
    from instagrapi.types import Media


class ExtractedRecipe(BaseModel):
    """Shape returned by OpenAI; validated before storing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    ingredients: list[str]
    instructions: list[str]

    # Primary classifications
    dish_type: str
    meal_type: str
    cuisine_type: str
    difficulty: str

    # Ingredient breakdown
    proteins: list[str]
    vegetables: list[str]
    grains_starches: list[str]
    herbs_spices: list[str]

    # Cooking details
    cooking_methods: list[str]
    equipment: list[str]

    # Time and serving
    prep_time: str
    cook_time: str
    total_time: str
    servings: str

    # Experience tags
    temperature: str
    texture: list[str]
    flavor_profile: list[str]

    # Dietary and lifestyle
    dietary_tags: list[str]
    health_tags: list[str]

    # Context and occasion
    season: list[str]
    occasion: list[str]
    skill_level: str

    # Special characteristics
    style_tags: list[str]
    prep_style: list[str]


class Recipe(BaseModel):
    """A structured, richly tagged recipe extracted from an Instagram post."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Identity
    code: str
    pk: str
    post_url: str
    caption: str | None

    # Core content
    title: str
    ingredients: list[str]
    instructions: list[str]

    # Classifications (use enums, default UNKNOWN)
    meal_type: MealType = MealType.UNKNOWN
    dish_type: DishType = DishType.UNKNOWN
    cuisine_type: CuisineType = CuisineType.UNKNOWN
    difficulty: Difficulty = Difficulty.UNKNOWN

    # Ingredient breakdown tags (open lists, not enums — they grow)
    proteins: list[str] = Field(default_factory=list)
    vegetables: list[str] = Field(default_factory=list)
    grains_starches: list[str] = Field(default_factory=list)
    herbs_spices: list[str] = Field(default_factory=list)

    # Cooking metadata
    cooking_methods: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    prep_time: str | None = None
    cook_time: str | None = None
    total_time: str | None = None
    servings: str | None = None
    base_servings: int | None = None

    # Experience / context tags
    temperature: str | None = None
    texture: list[str] = Field(default_factory=list)
    flavor_profile: list[str] = Field(default_factory=list)
    dietary_tags: list[str] = Field(default_factory=list)
    health_tags: list[str] = Field(default_factory=list)
    season: list[str] = Field(default_factory=list)
    occasion: list[str] = Field(default_factory=list)
    skill_level: str | None = None
    style_tags: list[str] = Field(default_factory=list)
    prep_style: list[str] = Field(default_factory=list)

    # Media
    cloudinary_url: str | None = None
    thumbnail_url: str | None = None

    # User edits (Phase 3)
    user_notes: str | None = None
    is_favorite: bool = False

    # Provenance
    is_recipe: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extracted_at: datetime | None = None
    model_used: str | None = None
    edited_by_user: bool = False

    @classmethod
    def from_extracted(
        cls,
        code: str,
        pk: str,
        caption: str | None,
        extracted: ExtractedRecipe,
        *,
        model_used: str | None = None,
    ) -> "Recipe":
        """Construct a Recipe from an ExtractedRecipe."""
        base_servings: int | None = None
        with contextlib.suppress(ValueError, TypeError):
            base_servings = int(extracted.servings)

        try:
            meal_type = MealType(extracted.meal_type)
        except ValueError:
            meal_type = MealType.UNKNOWN

        try:
            dish_type = DishType(extracted.dish_type)
        except ValueError:
            dish_type = DishType.UNKNOWN

        try:
            cuisine_type = CuisineType(extracted.cuisine_type)
        except ValueError:
            cuisine_type = CuisineType.UNKNOWN

        try:
            difficulty = Difficulty(extracted.difficulty)
        except ValueError:
            difficulty = Difficulty.UNKNOWN

        return cls(
            code=code,
            pk=pk,
            post_url=f"https://instagram.com/p/{code}/",
            caption=caption,
            title=extracted.title,
            ingredients=extracted.ingredients,
            instructions=extracted.instructions,
            meal_type=meal_type,
            dish_type=dish_type,
            cuisine_type=cuisine_type,
            difficulty=difficulty,
            proteins=extracted.proteins,
            vegetables=extracted.vegetables,
            grains_starches=extracted.grains_starches,
            herbs_spices=extracted.herbs_spices,
            cooking_methods=extracted.cooking_methods,
            equipment=extracted.equipment,
            prep_time=extracted.prep_time or None,
            cook_time=extracted.cook_time or None,
            total_time=extracted.total_time or None,
            servings=extracted.servings or None,
            base_servings=base_servings,
            temperature=extracted.temperature or None,
            texture=extracted.texture,
            flavor_profile=extracted.flavor_profile,
            dietary_tags=extracted.dietary_tags,
            health_tags=extracted.health_tags,
            season=extracted.season,
            occasion=extracted.occasion,
            skill_level=extracted.skill_level or None,
            style_tags=extracted.style_tags,
            prep_style=extracted.prep_style,
            model_used=model_used,
        )


class Collection(BaseModel):
    """Data model for an Instagram collection."""

    id: int | str
    post_pks: list[str] = []
    last_media_pk: int = 0
    name: str = ""
    type: str = ""
    media_count: int | None = None

    def append_posts(self, posts: "list[Media]") -> None:
        """Append new posts to the collection."""
        self.post_pks.extend(str(post.pk) for post in posts)
        if posts:
            self.last_media_pk = int(posts[-1].pk)
