from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import openai
from pydantic import BaseModel

from cookstagram.types import CuisineType, Difficulty, DishType, MealType, Media, Recipe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

    def analyze_post(self, post: Media) -> Recipe:
        """Analyze a single Instagram post to extract recipe information."""
        # First, determine if this is actually a recipe
        is_recipe, confidence = self._is_recipe_post(post.caption_text)

        if not is_recipe or confidence < 0.3:
            return Recipe(
                post_id=post.pk,
                code=post.code,
                caption=post.caption_text,
                title=post.title or "Not a recipe",
                is_recipe=False,
                confidence_score=confidence,
                analysis_notes="Post does not appear to contain a recipe",
            )

        # Extract recipe details
        recipe_data = self._extract_recipe_details(post.caption_text)
        confidence = recipe_data.pop("confidence_score", confidence)

        return Recipe(
            post_id=post.pk,
            code=post.code,
            caption=post.caption_text,
            is_recipe=True,
            confidence_score=confidence,
            **recipe_data,
        )

    def _is_recipe_post(self, caption: str) -> tuple[bool, float]:
        """Determine if the caption contains a recipe and confidence score."""
        prompt_template = Path("prompts/is_recipe.md").read_text()
        prompt = prompt_template.format(caption=caption)

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

        except Exception:
            logger.exception("Error in recipe detection")
            return False, 0.0

    def _extract_recipe_details(self, caption: str) -> dict:
        """Extract detailed recipe information from the caption."""
        prompt_template = Path("prompts/extract_details.md").read_text()
        prompt = prompt_template.format(caption=caption)

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

        except Exception:
            logger.exception("Error extracting recipe details")
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

    def analyze_posts_batch(self, posts: list[Media]) -> list[Recipe]:
        """Analyze multiple posts and return recipe data."""
        recipes = []

        for i, post in enumerate(posts, 1):
            logger.info("Analyzing post %d/%d: %s", i, len(posts), post.id)

            try:
                recipe = self.analyze_post(post)
                recipes.append(recipe)

                # Add a small delay to respect rate limits

                time.sleep(0.5)

            except Exception as e:
                logger.exception("Failed to analyze post %d", post.id)
                # Create a failed recipe entry
                recipes.append(
                    Recipe(
                        post_id=post.pk,
                        code=post.code,
                        caption=post.caption_text,
                        title="Analysis failed",
                        is_recipe=False,
                        confidence_score=0.0,
                        analysis_notes=f"Analysis failed: {e!s}",
                    ),
                )

        return recipes
