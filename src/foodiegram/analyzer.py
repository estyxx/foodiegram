from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from foodiegram.types import ExtractedRecipe, Recipe

if TYPE_CHECKING:
    from instagrapi.types import Media
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RecipeExtractorRealtime:
    """Analyzes Instagram posts to extract recipe information using Pydantic AI."""

    openai_api_key: str
    model_name: str = "gpt-4o-mini"
    recipe_extraction_agent: Agent[None, ExtractedRecipe]

    def __init__(self, api_key: str) -> None:
        """Initialize the analyzer with the OpenAI API key."""
        self.api_key = api_key

        # Setup agents for recipe detection and extraction
        self._setup_agents()

    def _setup_agents(self) -> None:
        """Set up the Pydantic AI agents for different tasks."""
        # Create the OpenAI model
        model = OpenAIModel(
            self.model_name,
            provider=OpenAIProvider(api_key=self.api_key),
        )

        # Agent for extracting detailed recipe information
        self.recipe_extraction_agent = Agent(
            model=model,
            output_type=ExtractedRecipe,
            system_prompt=(
                "You are an expert chef and recipe analyzer. "
                "Extract structured recipe data from social media text. "
                "Focus on practical tags for cooking and meal planning. "
                "Be as thorough as possible while maintaining accuracy."
            ),
        )

    def analyze_post(self, post: Media) -> Recipe | None:
        """Analyze a single Instagram post to extract recipe information."""
        try:
            recipe_details = self._extract_recipe_details(post.caption_text)
            if recipe_details:
                # Convert the structured response to Recipe model
                return self._create_recipe_from_details(
                    post=post,
                    details=recipe_details,
                )

        except Exception:
            logger.exception("Failed to analyze post %s", post.pk)

    def _extract_recipe_details(self, caption: str) -> ExtractedRecipe | None:
        """Extract detailed recipe information from the caption."""
        try:
            # Load prompt template
            prompt_template = Path(
                "src/foodiegram/prompts/extract_recipe_details.txt",
            ).read_text()
            prompt = prompt_template.format(caption=caption)

            # Use the agent to get structured response
            result = self.recipe_extraction_agent.run_sync(prompt)
        except Exception:
            logger.exception("Error extracting recipe details")
        else:
            return result.output

    def _create_recipe_from_details(
        self,
        post: Media,
        details: ExtractedRecipe,
    ) -> Recipe:
        """Convert ExtractedRecipe to Recipe model with enum validation."""
        # Convert string enums to enum objects with fallbacks

        return Recipe(
            post_id=post.pk,
            code=post.code,
            caption=post.caption_text,
            thumbnail_url=str(post.thumbnail_url),
            title=details.title,
            ingredients=details.ingredients,
            instructions=details.instructions,
            # Classifications
            dish_type=details.dish_type,
            meal_type=details.meal_type,
            cuisine_type=details.cuisine_type,
            difficulty=details.difficulty,
            # Time and servings
            cook_time=details.cook_time,
            prep_time=details.prep_time,
            total_time=details.total_time,
            servings=details.servings,
            # Enhanced ingredient tracking
            proteins=details.proteins,
            vegetables=details.vegetables,
            grains_starches=details.grains_starches,
            herbs_spices=details.herbs_spices,
            temperature=details.temperature,
            texture=details.texture,
            flavor_profile=details.flavor_profile,
            season=details.season,
            occasion=details.occasion,
            skill_level=details.skill_level,
            # Cooking details
            cooking_methods=details.cooking_methods,
            equipment=details.equipment,
            health_tags=details.health_tags,
            style_tags=details.style_tags,
            prep_style=details.prep_style,
            # Enhanced tagging
            dietary_tags=details.dietary_tags,
        )

    def analyze_posts(self, posts: list[Media]) -> list[Recipe]:
        """Analyze multiple posts and return recipe data."""
        recipes = []

        for i, post in enumerate(posts, 1):
            logger.info("Analyzing post %d/%d: %s", i, len(posts), post.id)

            try:
                recipe = self.analyze_post(post)
                recipes.append(recipe)

                # Add a small delay to respect rate limits
                time.sleep(0.5)

            except Exception:
                logger.exception("Failed to analyze post %s", post.id)

        return recipes
