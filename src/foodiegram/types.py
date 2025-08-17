from __future__ import annotations

from enum import Enum

from instagrapi.types import Media
from pydantic import BaseModel, Field


class MealType(str, Enum):
    """Types of meals."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DESSERT = "dessert"
    APPETIZER = "appetizer"


class DishType(str, Enum):
    """Types of dishes."""

    PASTA = "pasta"
    RISOTTO = "risotto"
    FISH = "fish"
    MEAT = "meat"
    CHICKEN = "chicken"
    BEEF = "beef"
    PORK = "pork"
    SEAFOOD = "seafood"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    SOUP = "soup"
    SALAD = "salad"
    BREAD = "bread"
    PIZZA = "pizza"
    SANDWICH = "sandwich"
    STIR_FRY = "stir_fry"
    CURRY = "curry"
    DESSERT = "dessert"
    SMOOTHIE = "smoothie"
    OTHER = "other"


class Difficulty(str, Enum):
    """Recipe difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class CuisineType(str, Enum):
    """Types of cuisine."""

    ITALIAN = "italian"
    ASIAN = "asian"
    CHINESE = "chinese"
    JAPANESE = "japanese"
    THAI = "thai"
    INDIAN = "indian"
    MEXICAN = "mexican"
    MEDITERRANEAN = "mediterranean"
    FRENCH = "french"
    AMERICAN = "american"
    MIDDLE_EASTERN = "middle_eastern"
    LATIN = "latin"
    AFRICAN = "african"
    OTHER = "other"


class Recipe(BaseModel):
    """Analyzed recipe data extracted from Instagram post."""

    # Original post data
    post_id: int
    code: str

    @property
    def post_url(self) -> str:
        """Construct the URL for the Instagram post."""
        return f"https://instagram.com/p/{self.code}"

    caption: str
    thumbnail_url: str | None = None

    # Extracted recipe information
    title: str
    ingredients: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)

    # Classifications
    main_protein: str | None = None
    dish_type: DishType | None = None
    meal_type: MealType | None = None
    cuisine_type: CuisineType | None = None
    difficulty: Difficulty | None = None

    # Additional metadata
    cooking_time: str | None = None
    prep_time: str | None = None
    servings: str | None = None
    dietary_tags: list[str] = Field(default_factory=list)

    # Analysis metadata
    is_recipe: bool = False
    confidence_score: float = 0.0
    analysis_notes: str | None = None

    # Enhanced ingredient tracking
    proteins: list[str] = Field(default_factory=list)
    vegetables: list[str] = Field(default_factory=list)
    key_ingredients: list[str] = Field(default_factory=list)

    # Cooking details
    cooking_method: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)

    # Enhanced tagging
    texture_tags: list[str] = Field(default_factory=list)
    flavor_tags: list[str] = Field(default_factory=list)
    season_tags: list[str] = Field(default_factory=list)
    occasion_tags: list[str] = Field(default_factory=list)

    # Better time tracking
    total_time: str | None = None


class Collection(BaseModel):
    """Data model for an Instagram collection."""

    id: int
    post_pks: list[str] = []
    last_media_pk: int = 0

    def append_posts(self, posts: list[Media]) -> None:
        """Append new posts to the collection."""
        self.post_pks.extend(str(post.pk) for post in posts)
        if posts:
            self.last_media_pk = int(posts[-1].pk)
