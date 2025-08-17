from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Post(BaseModel):
    """Data model for an Instagram post."""

    id: str
    taken_at: datetime.datetime

    url: str
    caption: str
    title: str | None = None
    image_path: Path | None
    thumbnail_url: str | None


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
