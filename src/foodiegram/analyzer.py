from __future__ import annotations

import logging
import time
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from foodiegram.types import CuisineType, Difficulty, DishType, MealType, Media, Recipe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Response models for structured AI responses
class RecipeDetectionResponse(BaseModel):
    """Response model for recipe detection."""

    is_recipe: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str


class RecipeDetailsResponse(BaseModel):
    """Response model for detailed recipe extraction."""

    title: str
    ingredients: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)

    # Classifications
    main_protein: str | None = None
    dish_type: str | None = None
    meal_type: str | None = None
    cuisine_type: str | None = None
    difficulty: str | None = None

    # Time and servings
    cooking_time: str | None = None
    prep_time: str | None = None
    total_time: str | None = None
    servings: str | None = None

    # Enhanced ingredient tracking
    proteins: list[str] = Field(default_factory=list)
    vegetables: list[str] = Field(default_factory=list)
    key_ingredients: list[str] = Field(default_factory=list)

    # Cooking details
    cooking_method: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)

    # Enhanced tagging
    dietary_tags: list[str] = Field(default_factory=list)
    texture_tags: list[str] = Field(default_factory=list)
    flavor_tags: list[str] = Field(default_factory=list)
    season_tags: list[str] = Field(default_factory=list)
    occasion_tags: list[str] = Field(default_factory=list)

    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)


class RecipeAnalyzer:
    """Analyzes Instagram posts to extract recipe information using Pydantic AI."""

    openai_api_key: str
    model_name: str = "gpt-4o-mini"
    recipe_detection_agent: Agent | None = None
    recipe_extraction_agent: Agent | None = None

    def __init__(self, openai_api_key: str) -> None:
        """Initialize the analyzer with the OpenAI API key."""
        self.openai_api_key = openai_api_key

        # Setup agents for recipe detection and extraction
        self._setup_agents()

    def __post_init__(self) -> None:
        """Initialize Pydantic AI agents."""
        self._setup_agents()

    def model_post_init(self, __context) -> None:
        """Pydantic v2 post-init hook."""
        self._setup_agents()

    def _setup_agents(self) -> None:
        """Setup the Pydantic AI agents for different tasks."""
        # Create the OpenAI model
        model = OpenAIModel(
            self.model_name,
            provider=OpenAIProvider(api_key=self.openai_api_key),
        )

        # Agent for detecting if a post contains a recipe
        self.recipe_detection_agent = Agent(
            model=model,
            output_type=RecipeDetectionResponse,
            system_prompt="""You are an expert at identifying recipe content in social media posts.
            Analyze the given Instagram caption and determine if it contains cooking instructions or recipe information.
            Be thorough but conservative in your assessment.""",
        )

        # Agent for extracting detailed recipe information
        self.recipe_extraction_agent = Agent(
            model=model,
            output_type=RecipeDetailsResponse,
            system_prompt="""You are an expert chef and recipe analyzer. Extract structured recipe data from social media text.
            Focus on practical tags for cooking and meal planning. Be as thorough as possible while maintaining accuracy.""",
        )

    def analyze_post(self, post: Media) -> Recipe:
        """Analyze a single Instagram post to extract recipe information."""
        try:
            # First, determine if this is actually a recipe
            detection_result = self._is_recipe_post(post.caption_text)

            if not detection_result.is_recipe or detection_result.confidence < 0.3:
                return Recipe(
                    post_id=post.pk,
                    code=post.code,
                    thumbnail_url=str(post.thumbnail_url),
                    caption=post.caption_text,
                    title=post.title or "Not a recipe",
                    is_recipe=False,
                    confidence_score=detection_result.confidence,
                    analysis_notes="Post does not appear to contain a recipe",
                )

            # Extract recipe details
            recipe_details = self._extract_recipe_details(post.caption_text)

            # Convert the structured response to Recipe model
            return self._create_recipe_from_details(
                post=post,
                details=recipe_details,
                detection_confidence=detection_result.confidence,
            )

        except Exception as e:
            logger.exception("Failed to analyze post %s", post.pk)
            return Recipe(
                post_id=post.pk,
                code=post.code,
                caption=post.caption_text,
                title="Analysis failed",
                is_recipe=False,
                confidence_score=0.0,
                analysis_notes=f"Analysis failed: {e!s}",
                thumbnail_url=str(post.thumbnail_url),
            )

    def _is_recipe_post(self, caption: str) -> RecipeDetectionResponse:
        """Determine if the caption contains a recipe and confidence score."""
        try:
            # Load prompt template
            prompt_template = Path("src/foodiegram/prompts/is_recipe.md").read_text()
            prompt = prompt_template.format(caption=caption)

            # Use the agent to get structured response
            result = self.recipe_detection_agent.run_sync(prompt)
            return result.output

        except Exception as e:
            logger.exception("Error in recipe detection")
            return RecipeDetectionResponse(
                is_recipe=False,
                confidence=0.0,
                reasoning=f"Error during analysis: {e}",
            )

    def _extract_recipe_details(self, caption: str) -> RecipeDetailsResponse:
        """Extract detailed recipe information from the caption."""
        try:
            # Load prompt template
            prompt_template = Path(
                "src/foodiegram/prompts/extract_details.md",
            ).read_text()
            prompt = prompt_template.format(caption=caption)

            # Use the agent to get structured response
            result = self.recipe_extraction_agent.run_sync(prompt)
            return result.output

        except Exception:
            logger.exception("Error extracting recipe details")
            return RecipeDetailsResponse(
                title="Failed to extract",
                confidence_score=0.0,
            )

    def _create_recipe_from_details(
        self,
        post: Media,
        details: RecipeDetailsResponse,
        detection_confidence: float,
    ) -> Recipe:
        """Convert RecipeDetailsResponse to Recipe model with enum validation."""
        # Convert string enums to enum objects with fallbacks
        dish_type = None
        if details.dish_type:
            try:
                dish_type = DishType(details.dish_type)
            except ValueError:
                logger.warning("Unknown dish_type: %s", details.dish_type)
                dish_type = DishType.OTHER

        meal_type = None
        if details.meal_type:
            try:
                meal_type = MealType(details.meal_type)
            except ValueError:
                logger.warning("Unknown meal_type: %s", details.meal_type)

        cuisine_type = None
        if details.cuisine_type:
            try:
                cuisine_type = CuisineType(details.cuisine_type)
            except ValueError:
                logger.warning("Unknown cuisine_type: %s", details.cuisine_type)
                cuisine_type = CuisineType.OTHER

        difficulty = None
        if details.difficulty:
            try:
                difficulty = Difficulty(details.difficulty)
            except ValueError:
                logger.warning("Unknown difficulty: %s", details.difficulty)

        # Set main_protein from proteins list if not explicitly set
        main_protein = details.main_protein
        if not main_protein and details.proteins:
            main_protein = details.proteins[0]

        return Recipe(
            post_id=post.pk,
            code=post.code,
            caption=post.caption_text,
            thumbnail_url=str(post.thumbnail_url),
            title=details.title,
            ingredients=details.ingredients,
            instructions=details.instructions,
            # Classifications
            main_protein=main_protein,
            dish_type=dish_type,
            meal_type=meal_type,
            cuisine_type=cuisine_type,
            difficulty=difficulty,
            # Time and servings
            cooking_time=details.cooking_time,
            prep_time=details.prep_time,
            total_time=details.total_time,
            servings=details.servings,
            # Enhanced ingredient tracking
            proteins=details.proteins,
            vegetables=details.vegetables,
            key_ingredients=details.key_ingredients,
            # Cooking details
            cooking_method=details.cooking_method,
            equipment=details.equipment,
            # Enhanced tagging
            dietary_tags=details.dietary_tags,
            texture_tags=details.texture_tags,
            flavor_tags=details.flavor_tags,
            season_tags=details.season_tags,
            occasion_tags=details.occasion_tags,
            # Analysis metadata
            is_recipe=True,
            confidence_score=max(detection_confidence, details.confidence_score),
        )

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
                logger.exception("Failed to analyze post %s", post.id)
                # Create a failed recipe entry
                recipes.append(
                    Recipe(
                        post_id=post.pk,
                        code=post.code,
                        caption=post.caption_text,
                        title="",
                        is_recipe=False,
                        confidence_score=0.0,
                        analysis_notes=f"Analysis failed: {e!s}",
                    ),
                )

        return recipes


# Async version for better performance
class AsyncRecipeAnalyzer(RecipeAnalyzer):
    """Async version of RecipeAnalyzer for better performance."""

    async def analyze_post_async(self, post: Media) -> Recipe:
        """Async version of analyze_post."""
        try:
            # First, determine if this is actually a recipe
            detection_result = await self._is_recipe_post_async(post.caption_text)

            if not detection_result.is_recipe or detection_result.confidence < 0.3:
                return Recipe(
                    post_id=post.pk,
                    code=post.code,
                    caption=post.caption_text,
                    title=post.title or "Not a recipe",
                    is_recipe=False,
                    confidence_score=detection_result.confidence,
                    analysis_notes="Post does not appear to contain a recipe",
                )

            # Extract recipe details
            recipe_details = await self._extract_recipe_details_async(post.caption_text)

            # Convert the structured response to Recipe model
            return self._create_recipe_from_details(
                post=post,
                details=recipe_details,
                detection_confidence=detection_result.confidence,
            )

        except Exception as e:
            logger.exception("Failed to analyze post %s", post.pk)
            return Recipe(
                post_id=post.pk,
                code=post.code,
                caption=post.caption_text,
                title="Analysis failed",
                is_recipe=False,
                confidence_score=0.0,
                analysis_notes=f"Analysis failed: {e!s}",
            )

    async def _is_recipe_post_async(self, caption: str) -> RecipeDetectionResponse:
        """Async version of recipe detection."""
        try:
            prompt_template = Path("prompts/is_recipe.md").read_text()
            prompt = prompt_template.format(caption=caption)

            result = await self.recipe_detection_agent.run(prompt)
            return result.data

        except Exception as e:
            logger.exception("Error in recipe detection")
            return RecipeDetectionResponse(
                is_recipe=False,
                confidence=0.0,
                reasoning=f"Error during analysis: {e}",
            )

    async def _extract_recipe_details_async(self, caption: str) -> RecipeDetailsResponse:
        """Async version of recipe details extraction."""
        try:
            prompt_template = Path("prompts/extract_details.md").read_text()
            prompt = prompt_template.format(caption=caption)

            result = await self.recipe_extraction_agent.run(prompt)
            return result.data

        except Exception:
            logger.exception("Error extracting recipe details")
            return RecipeDetailsResponse(
                title="Failed to extract",
                confidence_score=0.0,
            )

    async def analyze_posts_batch_async(self, posts: list[Media]) -> list[Recipe]:
        """Async batch analysis with concurrent processing."""
        import asyncio

        async def analyze_with_delay(post: Media, delay: float) -> Recipe:
            await asyncio.sleep(delay)
            return await self.analyze_post_async(post)

        # Create tasks with staggered delays to respect rate limits
        tasks = [analyze_with_delay(post, i * 0.5) for i, post in enumerate(posts)]

        logger.info("Starting async analysis of %d posts", len(posts))
        results = await asyncio.gather(*tasks, return_exceptions=True)

        recipes = []
        for i, result in enumerate(results):
            if isinstance(result, Recipe):
                recipes.append(result)
            else:
                logger.error("Failed to analyze post %s: %s", posts[i].id, result)
                recipes.append(
                    Recipe(
                        post_id=posts[i].pk,
                        code=posts[i].code,
                        caption=posts[i].caption_text,
                        title="Analysis failed",
                        is_recipe=False,
                        confidence_score=0.0,
                        analysis_notes=f"Analysis failed: {result}",
                    ),
                )

        return recipes
