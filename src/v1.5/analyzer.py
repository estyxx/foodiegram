from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import openai
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


class BatchJobStatus(BaseModel):
    """Status tracking for batch jobs."""

    batch_id: str
    status: str  # validating, in_progress, completed, failed, etc.
    created_at: datetime
    completed_at: datetime | None = None
    request_counts: dict[str, int] = Field(default_factory=dict)
    total_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    progress_percentage: float = 0.0


class ProcessingMode(str):
    """Processing mode options."""

    BATCH = "batch"
    CONCURRENT = "concurrent"
    AUTO = "auto"  # Choose based on number of requests


class EnhancedRecipeAnalyzer:
    """Enhanced analyzer with batch processing capabilities."""

    def __init__(
        self,
        openai_api_key: str,
        model_name: str = "gpt-4o-mini",
        batch_size: int = 1000,
        enable_caching: bool = True,
    ) -> None:
        """Initialize the enhanced analyzer."""
        self.openai_api_key = openai_api_key
        self.model_name = model_name
        self.batch_size = batch_size
        self.enable_caching = enable_caching

        # Initialize OpenAI client for batch operations
        self.openai_client = openai.OpenAI(api_key=openai_api_key)

        # Setup prompt templates
        self._load_prompt_templates()

        # Setup Pydantic AI agents
        self._setup_agents()

        # Create cache directory
        self.cache_dir = Path("cache/analysis")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Enhanced Recipe Analyzer initialized with {model_name}")

    def _load_prompt_templates(self) -> None:
        """Load prompt templates from files."""
        prompts_dir = Path("src/foodiegram/prompts")

        # Load or create default prompts
        self.recipe_detection_prompt = self._load_or_create_prompt(
            prompts_dir / "is_recipe.md",
            self._default_recipe_detection_prompt(),
        )

        self.recipe_extraction_prompt = self._load_or_create_prompt(
            prompts_dir / "extract_details.md",
            self._default_recipe_extraction_prompt(),
        )

    def _load_or_create_prompt(self, path: Path, default_content: str) -> str:
        """Load prompt from file or create with default content."""
        try:
            if path.exists():
                return path.read_text()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(default_content)
            logger.info(f"Created default prompt template: {path}")
            return default_content
        except Exception as e:
            logger.warning(f"Could not load prompt from {path}: {e}. Using default.")
            return default_content

    def _default_recipe_detection_prompt(self) -> str:
        """Default recipe detection prompt."""
        return """
Analyze this Instagram caption and determine if it contains a recipe or cooking instructions.

Caption: "{caption}"

Look for:
- Ingredient lists (even informal ones)
- Cooking steps/instructions
- Food preparation methods
- Recipe-related keywords (cook, bake, mix, sauté, etc.)
- Measurements (cups, tbsp, minutes, degrees, etc.)
- Cooking equipment mentions

Respond with your analysis of whether this is a recipe and your confidence level.
"""

    def _default_recipe_extraction_prompt(self) -> str:
        """Default recipe extraction prompt."""
        return """
Extract comprehensive recipe information from this Instagram caption. Focus on practical, useful tags for cooking and meal planning.

Caption: "{caption}"

Extract ALL available information, being thorough but accurate:

TRANSLATION RULE: Convert ALL Italian terms to English equivalents:
- "pomodoro" → "tomato"
- "zucchine" → "zucchini"
- "aglio" → "garlic"
- "cipolla" → "onion"
- "basilico" → "basil"
- "parmigiano" → "parmesan"
- "olio d'oliva" → "olive oil"
- "sale" → "salt"
- "pepe" → "pepper"

For vegetables, proteins, and key_ingredients - ONLY use English terms to avoid duplicates.

Provide comprehensive structured data including ingredients, cooking methods, equipment needed, dietary tags, and occasion tags.
"""

    def _setup_agents(self) -> None:
        """Setup Pydantic AI agents."""
        model = OpenAIModel(
            self.model_name,
            provider=OpenAIProvider(api_key=self.openai_api_key),
        )

        self.recipe_detection_agent = Agent(
            model=model,
            output_type=RecipeDetectionResponse,
            system_prompt="You are an expert at identifying recipe content in social media posts.",
        )

        self.recipe_extraction_agent = Agent(
            model=model,
            output_type=RecipeDetailsResponse,
            system_prompt="You are an expert chef and recipe analyzer. Extract structured recipe data with accurate English translations.",
        )

    # =====================================
    # BATCH PROCESSING IMPLEMENTATION
    # =====================================

    def analyze_posts_batch_mode(
        self,
        posts: list[Media],
        processing_mode: str = ProcessingMode.AUTO,
        progress_callback: callable | None = None,
    ) -> list[Recipe]:
        """Analyze posts using batch processing for cost optimization.

        Args:
        ----
            posts: List of Instagram posts to analyze
            processing_mode: 'batch', 'concurrent', or 'auto'
            progress_callback: Optional callback function for progress updates

        Returns:
        -------
            List of analyzed recipes

        """
        # Determine processing mode
        if processing_mode == ProcessingMode.AUTO:
            # Use batch for 20+ posts, concurrent for smaller batches
            processing_mode = (
                ProcessingMode.BATCH if len(posts) >= 20 else ProcessingMode.CONCURRENT
            )

        logger.info(f"Processing {len(posts)} posts using {processing_mode} mode")

        if processing_mode == ProcessingMode.BATCH:
            return self._process_with_batch_api(posts, progress_callback)
        return self._process_with_concurrent_api(posts, progress_callback)

    def _process_with_batch_api(
        self,
        posts: list[Media],
        progress_callback: callable | None = None,
    ) -> list[Recipe]:
        """Process posts using OpenAI Batch API."""
        logger.info(f"🚀 Starting batch processing for {len(posts)} posts")

        # Step 1: Create batch requests
        detection_requests, extraction_requests = self._create_batch_requests(posts)

        # Step 2: Process recipe detection batch
        if progress_callback:
            progress_callback("Creating recipe detection batch...", 0, len(posts))

        detection_results = self._submit_and_wait_for_batch(
            detection_requests,
            "recipe_detection",
            progress_callback,
        )

        # Step 3: Filter recipes and create extraction batch
        recipe_posts = self._filter_recipe_posts(posts, detection_results)
        logger.info(
            f"Found {len(recipe_posts)} potential recipes from {len(posts)} posts",
        )

        if not recipe_posts:
            logger.info("No recipes detected, returning empty results")
            return []

        # Step 4: Process recipe extraction batch
        if progress_callback:
            progress_callback(
                "Creating recipe extraction batch...",
                len(posts) // 2,
                len(posts),
            )

        extraction_batch_requests = self._create_extraction_requests(recipe_posts)
        extraction_results = self._submit_and_wait_for_batch(
            extraction_batch_requests,
            "recipe_extraction",
            progress_callback,
        )

        # Step 5: Combine results into Recipe objects
        recipes = self._combine_batch_results(
            posts,
            detection_results,
            extraction_results,
        )

        if progress_callback:
            progress_callback("Batch processing complete!", len(posts), len(posts))

        logger.info(f"✅ Batch processing complete! Analyzed {len(recipes)} recipes")
        return recipes

    def _create_batch_requests(
        self,
        posts: list[Media],
    ) -> tuple[list[dict], list[dict]]:
        """Create JSONL-formatted batch requests."""
        detection_requests = []
        extraction_requests = []

        for i, post in enumerate(posts):
            # Recipe detection request
            detection_req = {
                "custom_id": f"detection_{post.pk}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": self.model_name,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert at identifying recipe content in social media posts.",
                        },
                        {
                            "role": "user",
                            "content": self.recipe_detection_prompt.format(
                                caption=post.caption_text,
                            ),
                        },
                    ],
                    "response_format": {"type": "json_object"},
                },
            }
            detection_requests.append(detection_req)

            # Pre-create extraction request (will filter later)
            extraction_req = {
                "custom_id": f"extraction_{post.pk}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": self.model_name,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert chef and recipe analyzer. Extract structured recipe data with accurate English translations.",
                        },
                        {
                            "role": "user",
                            "content": self.recipe_extraction_prompt.format(
                                caption=post.caption_text,
                            ),
                        },
                    ],
                    "response_format": {"type": "json_object"},
                },
            }
            extraction_requests.append(extraction_req)

        return detection_requests, extraction_requests

    def _submit_and_wait_for_batch(
        self,
        requests: list[dict],
        batch_name: str,
        progress_callback: callable | None = None,
    ) -> dict[str, Any]:
        """Submit batch to OpenAI and wait for completion."""
        # Create JSONL file
        batch_file_path = self.cache_dir / f"{batch_name}_{int(time.time())}.jsonl"

        with open(batch_file_path, "w") as f:
            f.writelines(json.dumps(req) + "\n" for req in requests)

        logger.info(
            f"Created batch file: {batch_file_path} with {len(requests)} requests",
        )

        try:
            # Upload file
            batch_file = self.openai_client.files.create(
                file=open(batch_file_path, "rb"),
                purpose="batch",
            )

            # Create batch job
            batch_job = self.openai_client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h",
            )

            logger.info(f"Submitted batch job: {batch_job.id}")

            # Poll for completion
            return self._poll_batch_completion(
                batch_job.id,
                batch_name,
                progress_callback,
            )

        finally:
            # Clean up batch file
            if batch_file_path.exists():
                batch_file_path.unlink()

    def _poll_batch_completion(
        self,
        batch_id: str,
        batch_name: str,
        progress_callback: callable | None = None,
    ) -> dict[str, Any]:
        """Poll batch job until completion."""
        logger.info(f"Polling batch {batch_id} for completion...")
        start_time = time.time()

        while True:
            batch_status = self.openai_client.batches.retrieve(batch_id)

            # Update progress
            if progress_callback and hasattr(batch_status, "request_counts"):
                completed = getattr(batch_status.request_counts, "completed", 0)
                total = getattr(batch_status.request_counts, "total", 1)
                progress_callback(
                    f"Processing {batch_name} batch: {completed}/{total}",
                    completed,
                    total,
                )

            if batch_status.status == "completed":
                elapsed = time.time() - start_time
                logger.info(f"✅ Batch {batch_id} completed in {elapsed:.1f}s")

                # Download results
                result_file_id = batch_status.output_file_id
                result_content = self.openai_client.files.content(result_file_id)

                # Parse results
                results = {}
                for line in result_content.text.strip().split("\n"):
                    if line:
                        result_obj = json.loads(line)
                        custom_id = result_obj["custom_id"]
                        results[custom_id] = result_obj

                return results

            if batch_status.status in ["failed", "expired", "cancelled"]:
                logger.error(
                    f"❌ Batch {batch_id} failed with status: {batch_status.status}",
                )
                raise Exception(f"Batch processing failed: {batch_status.status}")

            logger.info(f"Batch {batch_id} status: {batch_status.status}")
            time.sleep(30)  # Poll every 30 seconds

    def _filter_recipe_posts(
        self,
        posts: list[Media],
        detection_results: dict,
    ) -> list[Media]:
        """Filter posts that are likely recipes based on detection results."""
        recipe_posts = []

        for post in posts:
            detection_key = f"detection_{post.pk}"
            if detection_key in detection_results:
                try:
                    response_content = detection_results[detection_key]["response"][
                        "choices"
                    ][0]["message"]["content"]
                    detection_data = json.loads(response_content)

                    is_recipe = detection_data.get("is_recipe", False)
                    confidence = detection_data.get("confidence", 0.0)

                    if is_recipe and confidence >= 0.3:
                        recipe_posts.append(post)

                except Exception as e:
                    logger.warning(
                        f"Error parsing detection result for post {post.pk}: {e}",
                    )

        return recipe_posts

    def _create_extraction_requests(self, recipe_posts: list[Media]) -> list[dict]:
        """Create extraction requests for confirmed recipe posts."""
        extraction_requests = []

        for post in recipe_posts:
            req = {
                "custom_id": f"extraction_{post.pk}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": self.model_name,
                    "temperature": 0.1,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert chef and recipe analyzer. Extract structured recipe data with accurate English translations.",
                        },
                        {
                            "role": "user",
                            "content": self.recipe_extraction_prompt.format(
                                caption=post.caption_text,
                            ),
                        },
                    ],
                    "response_format": {"type": "json_object"},
                },
            }
            extraction_requests.append(req)

        return extraction_requests

    def _combine_batch_results(
        self,
        posts: list[Media],
        detection_results: dict,
        extraction_results: dict,
    ) -> list[Recipe]:
        """Combine batch results into Recipe objects."""
        recipes = []

        for post in posts:
            try:
                detection_key = f"detection_{post.pk}"
                extraction_key = f"extraction_{post.pk}"

                # Get detection result
                if detection_key not in detection_results:
                    continue

                detection_content = detection_results[detection_key]["response"][
                    "choices"
                ][0]["message"]["content"]
                detection_data = json.loads(detection_content)

                is_recipe = detection_data.get("is_recipe", False)
                confidence = detection_data.get("confidence", 0.0)

                # Create recipe object
                if (
                    is_recipe
                    and confidence >= 0.3
                    and extraction_key in extraction_results
                ):
                    # Parse extraction result
                    extraction_content = extraction_results[extraction_key]["response"][
                        "choices"
                    ][0]["message"]["content"]
                    extraction_data = json.loads(extraction_content)

                    recipe = self._create_recipe_from_data(
                        post,
                        extraction_data,
                        confidence,
                    )
                    recipes.append(recipe)

                else:
                    # Create non-recipe entry
                    recipe = Recipe(
                        post_id=post.pk,
                        code=post.code,
                        caption=post.caption_text,
                        thumbnail_url=str(post.thumbnail_url),
                        title=post.title or "Not a recipe",
                        is_recipe=False,
                        confidence_score=confidence,
                    )
                    recipes.append(recipe)

            except Exception as e:
                logger.error(f"Error processing post {post.pk}: {e}")

                # Create error recipe
                recipe = Recipe(
                    post_id=post.pk,
                    code=post.code,
                    caption=post.caption_text,
                    thumbnail_url=str(post.thumbnail_url),
                    title="Analysis failed",
                    is_recipe=False,
                    confidence_score=0.0,
                    analysis_notes=f"Processing failed: {e}",
                )
                recipes.append(recipe)

        return recipes

    def _create_recipe_from_data(
        self,
        post: Media,
        data: dict,
        confidence: float,
    ) -> Recipe:
        """Create Recipe object from extracted data."""
        # Convert string enums with fallbacks
        dish_type = None
        if data.get("dish_type"):
            try:
                dish_type = DishType(data["dish_type"])
            except ValueError:
                dish_type = DishType.OTHER

        meal_type = None
        if data.get("meal_type"):
            try:
                meal_type = MealType(data["meal_type"])
            except ValueError:
                pass

        cuisine_type = None
        if data.get("cuisine_type"):
            try:
                cuisine_type = CuisineType(data["cuisine_type"])
            except ValueError:
                cuisine_type = CuisineType.OTHER

        difficulty = None
        if data.get("difficulty"):
            try:
                difficulty = Difficulty(data["difficulty"])
            except ValueError:
                pass

        return Recipe(
            post_id=post.pk,
            code=post.code,
            caption=post.caption_text,
            thumbnail_url=str(post.thumbnail_url),
            title=data.get("title", "Extracted Recipe"),
            ingredients=data.get("ingredients", []),
            instructions=data.get("instructions", []),
            # Classifications
            main_protein=data.get("main_protein"),
            dish_type=dish_type,
            meal_type=meal_type,
            cuisine_type=cuisine_type,
            difficulty=difficulty,
            # Time and servings
            cooking_time=data.get("cooking_time"),
            prep_time=data.get("prep_time"),
            total_time=data.get("total_time"),
            servings=data.get("servings"),
            # Enhanced ingredient tracking
            proteins=data.get("proteins", []),
            vegetables=data.get("vegetables", []),
            key_ingredients=data.get("key_ingredients", []),
            # Cooking details
            cooking_method=data.get("cooking_method", []),
            equipment=data.get("equipment", []),
            # Enhanced tagging
            dietary_tags=data.get("dietary_tags", []),
            texture_tags=data.get("texture_tags", []),
            flavor_tags=data.get("flavor_tags", []),
            season_tags=data.get("season_tags", []),
            occasion_tags=data.get("occasion_tags", []),
            # Analysis metadata
            is_recipe=True,
            confidence_score=max(confidence, data.get("confidence_score", 0.0)),
        )

    # =====================================
    # CONCURRENT PROCESSING (FALLBACK)
    # =====================================

    def _process_with_concurrent_api(
        self,
        posts: list[Media],
        progress_callback: callable | None = None,
    ) -> list[Recipe]:
        """Process posts using concurrent API calls (original method)."""
        logger.info(f"🔄 Using concurrent processing for {len(posts)} posts")

        recipes = []

        for i, post in enumerate(posts, 1):
            if progress_callback:
                progress_callback(f"Processing post {i}/{len(posts)}", i - 1, len(posts))

            try:
                recipe = self._analyze_single_post(post)
                recipes.append(recipe)

                # Rate limiting
                time.sleep(0.5)

            except Exception as e:
                logger.error(f"Failed to analyze post {post.pk}: {e}")

                recipe = Recipe(
                    post_id=post.pk,
                    code=post.code,
                    caption=post.caption_text,
                    thumbnail_url=str(post.thumbnail_url),
                    title="Analysis failed",
                    is_recipe=False,
                    confidence_score=0.0,
                    analysis_notes=f"Analysis failed: {e}",
                )
                recipes.append(recipe)

        if progress_callback:
            progress_callback("Concurrent processing complete!", len(posts), len(posts))

        return recipes

    def _analyze_single_post(self, post: Media) -> Recipe:
        """Analyze a single post using Pydantic AI agents."""
        # Check cache first
        if self.enable_caching:
            cached_recipe = self._get_cached_recipe(post.pk)
            if cached_recipe:
                return cached_recipe

        # Recipe detection
        detection_prompt = self.recipe_detection_prompt.format(caption=post.caption_text)
        detection_result = self.recipe_detection_agent.run_sync(detection_prompt)

        if (
            not detection_result.output.is_recipe
            or detection_result.output.confidence < 0.3
        ):
            recipe = Recipe(
                post_id=post.pk,
                code=post.code,
                caption=post.caption_text,
                thumbnail_url=str(post.thumbnail_url),
                title=post.title or "Not a recipe",
                is_recipe=False,
                confidence_score=detection_result.output.confidence,
            )
        else:
            # Recipe extraction
            extraction_prompt = self.recipe_extraction_prompt.format(
                caption=post.caption_text,
            )
            extraction_result = self.recipe_extraction_agent.run_sync(extraction_prompt)

            recipe = self._create_recipe_from_data(
                post,
                extraction_result.output.model_dump(),
                detection_result.output.confidence,
            )

        # Cache result
        if self.enable_caching:
            self._cache_recipe(recipe)

        return recipe

    # =====================================
    # CACHING SYSTEM
    # =====================================

    def _get_cached_recipe(self, post_id: int) -> Recipe | None:
        """Get cached recipe if available."""
        cache_file = self.cache_dir / f"recipe_{post_id}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                return Recipe(**data)
            except Exception as e:
                logger.warning(f"Error loading cached recipe {post_id}: {e}")
        return None

    def _cache_recipe(self, recipe: Recipe) -> None:
        """Cache recipe result."""
        cache_file = self.cache_dir / f"recipe_{recipe.post_id}.json"
        try:
            cache_file.write_text(json.dumps(recipe.model_dump(), default=str, indent=2))
        except Exception as e:
            logger.warning(f"Error caching recipe {recipe.post_id}: {e}")

    # =====================================
    # PROGRESS TRACKING & UTILITIES
    # =====================================

    def estimate_cost(
        self,
        posts: list[Media],
        processing_mode: str = ProcessingMode.AUTO,
    ) -> dict[str, float]:
        """Estimate processing costs."""
        if processing_mode == ProcessingMode.AUTO:
            processing_mode = (
                ProcessingMode.BATCH if len(posts) >= 20 else ProcessingMode.CONCURRENT
            )

        # Rough token estimates per request
        avg_input_tokens = 800  # System prompt + user caption
        avg_output_tokens = 400  # Structured response

        # Total requests (detection + extraction for each post)
        total_requests = len(posts) * 2
        total_input_tokens = total_requests * avg_input_tokens
        total_output_tokens = total_requests * avg_output_tokens

        # Pricing (gpt-4o-mini)
        if processing_mode == ProcessingMode.BATCH:
            # 50% discount for batch
            input_cost = (total_input_tokens / 1_000_000) * 0.075  # Batch rate
            output_cost = (total_output_tokens / 1_000_000) * 0.300  # Batch rate
        else:
            # Standard concurrent pricing
            input_cost = (total_input_tokens / 1_000_000) * 0.150  # Standard rate
            output_cost = (total_output_tokens / 1_000_000) * 0.600  # Standard rate

        total_cost = input_cost + output_cost

        return {
            "processing_mode": processing_mode,
            "total_posts": len(posts),
            "estimated_requests": total_requests,
            "estimated_input_tokens": total_input_tokens,
            "estimated_output_tokens": total_output_tokens,
            "estimated_input_cost": input_cost,
            "estimated_output_cost": output_cost,
            "estimated_total_cost": total_cost,
            "cost_per_recipe": total_cost / len(posts) if posts else 0,
        }

    def get_processing_recommendation(self, posts: list[Media]) -> dict[str, Any]:
        """Get recommendation for processing mode."""
        batch_estimate = self.estimate_cost(posts, ProcessingMode.BATCH)
        concurrent_estimate = self.estimate_cost(posts, ProcessingMode.CONCURRENT)

        savings = (
            concurrent_estimate["estimated_total_cost"]
            - batch_estimate["estimated_total_cost"]
        )
        savings_percentage = (
            savings / concurrent_estimate["estimated_total_cost"]
        ) * 100

        return {
            "posts_count": len(posts),
            "batch_cost": batch_estimate["estimated_total_cost"],
            "concurrent_cost": concurrent_estimate["estimated_total_cost"],
            "savings_amount": savings,
            "savings_percentage": savings_percentage,
            "recommended_mode": ProcessingMode.BATCH
            if len(posts) >= 10
            else ProcessingMode.CONCURRENT,
            "reasoning": (
                f"Batch mode will save ${savings:.2f} ({savings_percentage:.1f}%) "
                f"but takes up to 24 hours vs immediate results"
            ),
        }


# =====================================
# BACKWARDS COMPATIBILITY
# =====================================


class RecipeAnalyzer(EnhancedRecipeAnalyzer):
    """Backwards compatible analyzer class."""

    def analyze_posts_batch(self, posts: list[Media]) -> list[Recipe]:
        """Original method signature for backwards compatibility."""
        return self.analyze_posts_batch_mode(
            posts,
            processing_mode=ProcessingMode.CONCURRENT,
        )
