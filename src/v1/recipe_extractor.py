"""Instagram Recipe Extractor
A clean, modular system for extracting and analyzing saved Instagram recipes
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# Core Data Models
class MealType(Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"
    DESSERT = "dessert"


class DishType(Enum):
    PASTA = "pasta"
    RISOTTO = "risotto"
    FISH = "fish"
    MEAT = "meat"
    VEGETARIAN = "vegetarian"
    SOUP = "soup"
    SALAD = "salad"
    BREAD = "bread"


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass
class Recipe:
    """Core recipe data model"""

    id: str
    title: str
    caption: str
    image_urls: list[str]
    source_url: str
    username: str

    # Extracted content
    ingredients: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)

    # Classifications
    main_protein: str | None = None
    dish_type: DishType | None = None
    meal_type: MealType | None = None
    difficulty: Difficulty | None = None
    cooking_time: str | None = None

    # Metadata
    tags: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


# Core Interfaces
class DataExtractor:
    """Abstract base for Instagram data extraction"""

    def extract_saved_posts(self) -> list[dict[str, Any]]:
        """Extract raw saved posts data"""
        raise NotImplementedError

    def download_images(self, post: dict[str, Any], output_dir: Path) -> list[str]:
        """Download post images"""
        raise NotImplementedError


class ContentParser:
    """Abstract base for parsing recipe content from posts"""

    def parse_recipe(self, post_data: dict[str, Any]) -> Recipe:
        """Parse raw post data into Recipe object"""
        raise NotImplementedError

    def extract_ingredients(self, text: str) -> list[str]:
        """Extract ingredients from text"""
        raise NotImplementedError

    def extract_steps(self, text: str) -> list[str]:
        """Extract cooking steps from text"""
        raise NotImplementedError


class RecipeClassifier:
    """Abstract base for classifying recipes using LLM"""

    def classify_recipe(self, recipe: Recipe) -> Recipe:
        """Add classifications to recipe"""
        raise NotImplementedError


# Main Orchestrator
class RecipeExtractor:
    """Main orchestrator class"""

    def __init__(
        self,
        extractor: DataExtractor,
        parser: ContentParser,
        classifier: RecipeClassifier,
        output_dir: Path = Path("./recipes"),
    ):
        self.extractor = extractor
        self.parser = parser
        self.classifier = classifier
        self.output_dir = output_dir
        self.output_dir.mkdir(exist_ok=True)

        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def extract_all_recipes(self) -> list[Recipe]:
        """Main extraction pipeline"""
        self.logger.info("Starting recipe extraction...")

        # 1. Extract raw data
        raw_posts = self.extractor.extract_saved_posts()
        self.logger.info(f"Found {len(raw_posts)} saved posts")

        # 2. Parse recipes
        recipes = []
        for post in raw_posts:
            try:
                recipe = self.parser.parse_recipe(post)
                if self._is_recipe(recipe):  # Filter non-recipe posts
                    recipe = self.classifier.classify_recipe(recipe)
                    recipes.append(recipe)
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse post {post.get('id', 'unknown')}: {e}",
                )

        self.logger.info(f"Extracted {len(recipes)} recipes")

        # 3. Save results
        self._save_recipes(recipes)

        return recipes

    def _is_recipe(self, recipe: Recipe) -> bool:
        """Basic heuristic to filter recipe posts"""
        text = (recipe.title + " " + recipe.caption).lower()
        recipe_keywords = [
            "recipe",
            "ingredients",
            "cook",
            "bake",
            "minutes",
            "cup",
            "tbsp",
        ]
        return any(keyword in text for keyword in recipe_keywords)

    def _save_recipes(self, recipes: list[Recipe]):
        """Save recipes to JSON file"""
        output_file = self.output_dir / "recipes.json"

        # Convert to serializable format
        data = []
        for recipe in recipes:
            recipe_dict = {
                "id": recipe.id,
                "title": recipe.title,
                "caption": recipe.caption,
                "image_urls": recipe.image_urls,
                "source_url": recipe.source_url,
                "username": recipe.username,
                "ingredients": recipe.ingredients,
                "steps": recipe.steps,
                "main_protein": recipe.main_protein,
                "dish_type": recipe.dish_type.value if recipe.dish_type else None,
                "meal_type": recipe.meal_type.value if recipe.meal_type else None,
                "difficulty": recipe.difficulty.value if recipe.difficulty else None,
                "cooking_time": recipe.cooking_time,
                "tags": recipe.tags,
            }
            data.append(recipe_dict)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.logger.info(f"Saved {len(recipes)} recipes to {output_file}")


# Usage Example
if __name__ == "__main__":
    # This would be implemented with concrete classes
    from implementations import InstaloaderExtractor, LLMContentParser, OpenAIClassifier

    extractor = InstaloaderExtractor(username="your_username")
    parser = LLMContentParser()
    classifier = OpenAIClassifier()

    recipe_extractor = RecipeExtractor(extractor, parser, classifier)
    recipes = recipe_extractor.extract_all_recipes()

    print(f"Extracted {len(recipes)} recipes!")
