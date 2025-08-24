from __future__ import annotations

from enum import Enum

from instagrapi.types import Media
from pydantic import BaseModel


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
    """Simple recipe model that works with OpenAI strict mode."""

    # ALL FIELDS REQUIRED - NO OPTIONALS!
    title: str
    ingredients: list[str]
    instructions: list[str]
    cuisine_type: str  # "italian", "asian", "other"
    difficulty: str  # "easy", "medium", "hard"
    main_protein: str  # "chicken", "beef", "vegetarian", "none"
    cooking_method: str  # "baking", "frying", "boiling", "other"
    is_recipe: bool
    confidence_score: float  # 0.0 to 1.0

    @classmethod
    def model_json_schema_strict(cls) -> dict[str, object]:
        """Generate JSON schema with additionalProperties: false for OpenAI strict mode."""
        schema = cls.model_json_schema()

        def make_strict(obj: object) -> object:
            if isinstance(obj, dict):
                if obj.get("type") == "object":
                    obj["additionalProperties"] = False
                for value in obj.values():
                    make_strict(value)
            elif isinstance(obj, list):
                for item in obj:
                    make_strict(item)
            return obj

        return make_strict(schema)


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
