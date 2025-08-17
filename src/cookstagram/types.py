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
    post_id: str
    post_url: str
    caption: str

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
