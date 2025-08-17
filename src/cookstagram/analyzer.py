from __future__ import annotations

import json
import traceback

import openai
from pydantic import BaseModel

from cookstagram.types import CuisineType, Difficulty, DishType, MealType, Post, Recipe


class RecipeAnalyzer(BaseModel):
    """Analyzes Instagram posts to extract recipe information using OpenAI."""

    openai_api_key: str
    model: str = "gpt-4o-mini"
    _client: openai.OpenAI | None = None

    def __post_init__(self) -> None:
        """Initialize OpenAI client."""
        self._client = openai.OpenAI(
            # This is the default and can be omitted
            api_key=self.openai_api_key,
        )

    @property
    def client(self) -> openai.OpenAI:
        """Lazy load the OpenAI client."""
        if self._client is None:
            self._client = openai.OpenAI(api_key=self.openai_api_key)
        return self._client

    def analyze_post(self, post: Post) -> Recipe:
        """Analyze a single Instagram post to extract recipe information."""
        # First, determine if this is actually a recipe
        is_recipe, confidence = self._is_recipe_post(post.caption)

        if not is_recipe or confidence < 0.3:
            return Recipe(
                post_id=post.id,
                post_url=post.url,
                caption=post.caption,
                title=post.title or "Not a recipe",
                is_recipe=False,
                confidence_score=confidence,
                analysis_notes="Post does not appear to contain a recipe",
            )

        # Extract recipe details
        recipe_data = self._extract_recipe_details(post.caption)
        confidence = recipe_data.pop("confidence_score", confidence)
        return Recipe(
            post_id=post.id,
            post_url=post.url,
            caption=post.caption,
            is_recipe=True,
            confidence_score=confidence,
            **recipe_data,
        )

    def _is_recipe_post(self, caption: str) -> tuple[bool, float]:
        """Determine if the caption contains a recipe and confidence score."""
        prompt = f"""
        Analyze this Instagram caption and determine if it contains a recipe or cooking instructions.

        Caption: "{caption}"

        Respond with JSON in this exact format:
        {{
            "is_recipe": true/false,
            "confidence": 0.0-1.0,
            "reasoning": "brief explanation"
        }}

        Look for:
        - Ingredient lists
        - Cooking steps/instructions
        - Food preparation methods
        - Recipe-related keywords (cook, bake, mix, etc.)
        - Measurements (cups, tbsp, minutes, etc.)
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at identifying recipe content in social media posts.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )

            content = self._clean_markdown(response.choices[0].message.content.strip())
            result = json.loads(content)
            return result["is_recipe"], result["confidence"]

        except Exception as e:
            print(f"Error in recipe detection: {e}")
            traceback.print_exc()
            return False, 0.0

    def _extract_recipe_details(self, caption: str) -> dict:
        """Extract detailed recipe information from the caption."""
        prompt = f"""
        Extract recipe information from this Instagram caption. Be as thorough as possible.

        Caption: "{caption}"

        Respond with JSON in this exact format:
        {{
            "title": "recipe name/title",
            "ingredients": ["ingredient 1", "ingredient 2", ...],
            "instructions": ["step 1", "step 2", ...],
            "main_protein": "chicken/beef/fish/tofu/eggs/none/etc",
            "dish_type": "pasta/soup/salad/meat/fish/vegetarian/vegan/dessert/other",
            "meal_type": "breakfast/lunch/dinner/snack/dessert/appetizer",
            "cuisine_type": "italian/asian/mexican/american/mediterranean/other",
            "difficulty": "easy/medium/hard",
            "cooking_time": "estimated time or null",
            "prep_time": "estimated time or null",
            "servings": "number of servings or null",
            "dietary_tags": ["vegetarian", "vegan", "gluten-free", "dairy-free", "keto", "healthy", ...],
            "confidence_score": 0.0-1.0
        }}

        Guidelines:
        - Extract ingredients even if not in a perfect list format
        - Look for cooking steps/methods in the text
        - Infer dish type from ingredients and methods
        - Be conservative with difficulty assessment
        - Include dietary tags based on ingredients
        - If information is unclear, use null or "other"
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert chef and recipe analyzer. Extract structured recipe data from text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )

            # Clean markdown code block if present
            content = self._clean_markdown(response.choices[0].message.content.strip())
            result = json.loads(content)

            # Convert string enums to enum objects
            if result.get("dish_type"):
                try:
                    result["dish_type"] = DishType(result["dish_type"])
                except ValueError:
                    result["dish_type"] = DishType.OTHER

            if result.get("meal_type"):
                try:
                    result["meal_type"] = MealType(result["meal_type"])
                except ValueError:
                    result["meal_type"] = None

            if result.get("cuisine_type"):
                try:
                    result["cuisine_type"] = CuisineType(result["cuisine_type"])
                except ValueError:
                    result["cuisine_type"] = CuisineType.OTHER

            if result.get("difficulty"):
                try:
                    result["difficulty"] = Difficulty(result["difficulty"])
                except ValueError:
                    result["difficulty"] = None

            return result

        except Exception as e:
            print(f"Error extracting recipe details: {e}")
            traceback.print_exc()
            return {
                "title": "Failed to extract",
                "ingredients": [],
                "instructions": [],
                "confidence_score": 0.0,
            }

    def _clean_markdown(self, content: str) -> str:
        """Remove markdown formatting from the content."""
        if content.startswith("```"):
            # Remove triple backticks and possible language hint (e.g., ```json)
            lines = content.splitlines()
            # Remove first line (```json or ```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            return "\n".join(lines).strip()
        return content

    def analyze_posts_batch(self, posts: list[Post]) -> list[Recipe]:
        """Analyze multiple posts and return recipe data."""
        recipes = []

        for i, post in enumerate(posts, 1):
            print(f"Analyzing post {i}/{len(posts)}: {post.id}")

            try:
                recipe = self.analyze_post(post)
                recipes.append(recipe)

                # Add a small delay to respect rate limits
                import time

                time.sleep(0.5)

            except Exception as e:
                print(f"Failed to analyze post {post.id}: {e}")
                traceback.print_exc()
                # Create a failed recipe entry
                recipes.append(
                    Recipe(
                        post_id=post.id,
                        post_url=post.url,
                        caption=post.caption,
                        title="Analysis failed",
                        is_recipe=False,
                        confidence_score=0.0,
                        analysis_notes=f"Analysis failed: {e!s}",
                    ),
                )

        return recipes
