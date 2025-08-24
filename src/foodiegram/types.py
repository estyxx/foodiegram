from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from instagrapi.types import Media


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


class ExtractedRecipe(BaseModel):
    """Extracted recipe data model."""

    # necessary to add additionalProperties field
    model_config = ConfigDict(extra="forbid")

    title: str
    ingredients: list[str]
    instructions: list[str]

    # Primary classifications
    cuisine_type: str
    difficulty: str
    meal_type: str

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
    """Recipe data model including source post info."""

    # Original post data
    post_id: int
    code: str

    @property
    def post_url(self) -> str:
        """Construct the URL for the Instagram post."""
        return f"https://instagram.com/p/{self.code}"

    caption: str
    thumbnail_url: str | None = None

    title: str
    ingredients: list[str]
    instructions: list[str]

    # Primary classifications
    cuisine_type: str
    difficulty: str
    meal_type: str

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


class Collection(BaseModel):
    """Data model for an Instagram collection."""

    id: int | str
    post_pks: list[str] = []
    last_media_pk: int = 0
    name: str = ""
    type: str = ""
    media_count: int | None = None

    def append_posts(self, posts: list[Media]) -> None:
        """Append new posts to the collection."""
        self.post_pks.extend(str(post.pk) for post in posts)
        if posts:
            self.last_media_pk = int(posts[-1].pk)
