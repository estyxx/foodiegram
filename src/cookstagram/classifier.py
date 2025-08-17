import json
import re
from enum import Enum
from typing import Any

import openai
from pydantic import BaseModel, Field


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


class Recipe(BaseModel):
    """Recipe data model"""

    id: str
    title: str
    caption: str
    image_urls: list[str]
    source_url: str
    username: str

    # Extracted content
    ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)

    # Classifications
    main_protein: str | None = None
    dish_type: DishType | None = None
    meal_type: MealType | None = None
    difficulty: Difficulty | None = None
    cooking_time: str | None = None

    # Metadata
    tags: list[str] = Field(default_factory=list)
    raw_data: dict[str, Any] = Field(default_factory=dict)


class OpenAIClassifier:
    """Classify recipes using OpenAI API"""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def classify_recipe(self, recipe: Recipe) -> Recipe:
        """Classify recipe using GPT."""
        prompt = self._build_classification_prompt(recipe)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a expert chef and recipe analyzer. Analyze recipes and provide structured classifications.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )

            result = response.choices[0].message.content
            return self._parse_classification_result(recipe, result)

        except Exception as e:
            print(f"Classification failed for {recipe.id}: {e}")
            return recipe

    def _build_classification_prompt(self, recipe: Recipe) -> str:
        """Build prompt for recipe classification"""
        return f"""
Analyze this recipe and provide a JSON response with the following classifications:

RECIPE DATA:
Title: {recipe.title}
Ingredients: {", ".join(recipe.ingredients[:10])}  # First 10 ingredients
Steps: {". ".join(recipe.steps[:3])}  # First 3 steps
Caption: {recipe.caption[:500]}...  # Truncated

Please respond with JSON in this exact format:
{{
    "main_protein": "chicken|beef|pork|fish|seafood|eggs|tofu|beans|nuts|none",
    "dish_type": "pasta|risotto|soup|salad|bread|meat|fish|vegetarian|dessert|snack|other",
    "meal_type": "breakfast|lunch|dinner|snack|dessert",
    "difficulty": "easy|medium|hard",
    "cooking_time": "estimated time like '30 minutes' or 'unknown'",
    "cuisine_type": "italian|asian|mexican|indian|american|mediterranean|other",
    "dietary_tags": ["vegetarian", "vegan", "gluten-free", "dairy-free", "keto", "low-carb", "healthy"],
    "confidence": 0.9
}}

Base your analysis on the ingredients and cooking methods described.
"""

    def _parse_classification_result(self, recipe: Recipe, result: str) -> Recipe:
        """Parse GPT response and update recipe"""
        try:
            # Extract JSON from response
            json_match = re.search(r"\{.*\}", result, re.DOTALL)
            if not json_match:
                return recipe

            classification = json.loads(json_match.group())

            # Map string values to enums
            if classification.get("dish_type"):
                try:
                    recipe.dish_type = DishType(classification["dish_type"])
                except ValueError:
                    pass

            if classification.get("meal_type"):
                try:
                    recipe.meal_type = MealType(classification["meal_type"])
                except ValueError:
                    pass

            if classification.get("difficulty"):
                try:
                    recipe.difficulty = Difficulty(classification["difficulty"])
                except ValueError:
                    pass

            # Direct assignments
            recipe.main_protein = classification.get("main_protein")
            recipe.cooking_time = classification.get("cooking_time")

            # Add dietary tags to existing tags
            dietary_tags = classification.get("dietary_tags", [])
            recipe.tags.extend(dietary_tags)

            return recipe

        except Exception as e:
            print(f"Failed to parse classification for {recipe.id}: {e}")
            return recipe
