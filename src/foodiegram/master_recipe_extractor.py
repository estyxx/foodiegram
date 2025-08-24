import json
import logging
import time
from pathlib import Path

from openai import OpenAI
from openai.types import Batch
from pydantic import BaseModel, ConfigDict

from foodiegram.types import Media

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Recipe(BaseModel):
    """Comprehensive recipe model optimized for filtering and discovery."""

    model_config = ConfigDict(extra="forbid")

    # Core recipe data
    title: str
    ingredients: list[str]
    instructions: list[str]

    # Primary classifications
    cuisine_type: str  # "italian", "asian", "mediterranean", "fusion", "other"
    difficulty: str  # "easy", "medium", "hard"
    meal_type: str  # "breakfast", "lunch", "dinner", "snack", "dessert", "appetizer"

    # Detailed ingredient breakdown (English only)
    proteins: list[str]  # ["chicken", "beef", "fish", "tofu", "eggs", "cheese"]
    vegetables: list[str]  # ["tomato", "onion", "garlic", "zucchini", "spinach"]
    grains_starches: list[str]  # ["pasta", "rice", "bread", "potatoes", "quinoa"]
    herbs_spices: list[str]  # ["basil", "oregano", "garlic", "paprika", "cumin"]

    # Cooking details
    cooking_methods: list[
        str
    ]  # ["baking", "frying", "grilling", "boiling", "sautéing", "roasting"]
    equipment: list[
        str
    ]  # ["oven", "pan", "blender", "grill", "slow_cooker", "air_fryer"]

    # Time and serving
    prep_time: str  # "15 minutes", "30 minutes", "1 hour", "unknown"
    cook_time: str  # "20 minutes", "45 minutes", "2 hours", "unknown"
    total_time: str  # "35 minutes", "1.5 hours", "unknown"
    servings: str  # "2-4", "6-8", "1", "unknown"

    # Experience tags
    temperature: str  # "hot", "cold", "room_temperature", "both"
    texture: list[str]  # ["crispy", "creamy", "crunchy", "smooth", "chewy", "tender"]
    flavor_profile: list[str]  # ["savory", "sweet", "spicy", "tangy", "umami", "bitter"]

    # Dietary and lifestyle
    dietary_tags: list[
        str
    ]  # ["vegetarian", "vegan", "gluten_free", "dairy_free", "keto", "paleo"]
    health_tags: list[
        str
    ]  # ["low_calorie", "high_protein", "low_carb", "heart_healthy", "diabetic_friendly"]

    # Context and occasion
    season: list[str]  # ["spring", "summer", "fall", "winter", "year_round"]
    occasion: list[
        str
    ]  # ["weeknight", "weekend", "party", "holiday", "date_night", "meal_prep"]
    skill_level: str  # "beginner", "intermediate", "advanced"

    # Special characteristics
    style_tags: list[
        str
    ]  # ["comfort_food", "gourmet", "rustic", "modern", "traditional", "fusion"]
    prep_style: list[str]  # ["make_ahead", "quick", "one_pot", "no_cook", "batch_cook"]


class MasterRecipeExtractor:
    """Master recipe extraction system optimized for comprehensive data extraction
    with Italian→English translation and rich tagging.
    """

    def __init__(self, api_key: str, model: str = "gpt-4.1") -> None:
        """Initialize extractor.

        Args:
        ----
            api_key: OpenAI API key
            model: Model to use - "gpt-4.1" (recommended) or "gpt-4o-mini" (cheaper)

        """
        self._client = OpenAI(api_key=api_key)
        self.model = model
        logger.info("Initialized MasterRecipeExtractor with %s", model)

    def create_batch(self, posts: list[Media]) -> str:
        """Create batch job for recipe extraction."""
        tasks_path = Path("data/tasks.jsonl")
        tasks_path.parent.mkdir(exist_ok=True)

        # Load comprehensive prompt
        instruction = Path("src/foodiegram/prompts/details.md").read_text()
        schema = Recipe.model_json_schema()

        with tasks_path.open("w") as f:
            for post in posts:
                if not post.caption_text.strip():
                    continue

                line = {
                    "custom_id": f"recipe-{post.id}",
                    "method": "POST",
                    "url": "/v1/responses",
                    "body": {
                        "model": self.model,
                        "input": instruction.format(caption=post.caption_text),
                        "text": {
                            "format": {
                                "type": "json_schema",
                                "name": "ComprehensiveRecipe",
                                "schema": schema,
                                "strict": True,
                            },
                        },
                    },
                }
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

        logger.info("Created %d tasks", len(list(tasks_path.open())) - 1)

        # Upload and create batch
        with tasks_path.open("rb") as f:
            upload = self._client.files.create(file=f, purpose="batch")

        batch = self._client.batches.create(
            input_file_id=upload.id,
            endpoint="/v1/responses",
            completion_window="24h",
        )
        return batch.id

    def wait_for_batch(self, batch_id: str) -> Batch:
        """Wait for batch completion with progress updates."""
        logger.info("Waiting for batch %s...", batch_id)
        start_time = time.time()

        while True:
            batch = self._client.batches.retrieve(batch_id)
            elapsed = time.time() - start_time

            # Show progress if available
            if hasattr(batch, "request_counts") and batch.request_counts:
                completed = getattr(batch.request_counts, "completed", 0)
                total = getattr(batch.request_counts, "total", 0)
                if total > 0:
                    progress = (completed / total) * 100
                    logger.info(
                        "Progress: %d/%d (%.1f%%) - %.0fs elapsed",
                        completed,
                        total,
                        progress,
                        elapsed,
                    )

            if batch.status in {"completed", "failed", "cancelled", "expired"}:
                logger.info("Batch %s after %.1fs", batch.status, elapsed)
                return batch

            time.sleep(30)

    def download_results(self, batch: Batch) -> None:
        """Download batch results and return file paths."""
        results_path = Path("data/results.jsonl")
        errors_path = Path("data/errors.jsonl")

        if batch.error_file_id:
            content = self._client.files.content(batch.error_file_id).text
            errors_path.write_text(content, encoding="utf-8")
            logger.info("Downloaded errors to %s", errors_path)

        if batch.output_file_id:
            content = self._client.files.content(batch.output_file_id).text
            results_path.write_text(content, encoding="utf-8")
            logger.info("Downloaded results to %s", results_path)

    def parse_results(self, posts: list[Media]) -> list[Recipe]:
        """Parse batch results into Recipe objects with comprehensive data."""
        results_path = Path("data/results.jsonl")
        if not results_path.exists():
            logger.warning("Results file not found: %s", results_path)
            return []

        # Create post lookup
        post_lookup = {f"recipe-{post.id}": post for post in posts}
        recipes = []

        logger.info("Parsing results from %s", results_path)

        for line_num, line in enumerate(results_path.read_text().splitlines(), 1):
            if not line.strip():
                continue

            try:
                result = json.loads(line)
                custom_id = result["custom_id"]

                if custom_id not in post_lookup:
                    logger.warning("Unknown custom_id: %s", custom_id)
                    continue

                post = post_lookup[custom_id]

                # Extract recipe data from response
                response_body = result["response"]["body"]

                recipe_data = json.loads(
                    response_body["output"][0]["content"][0]["text"],
                )

                # Create Recipe object
                recipe = Recipe(**recipe_data)
                recipes.append(recipe)

            except Exception:
                logger.exception("Error parsing line %d", line_num)
                continue

        logger.info("Successfully parsed %d recipes", len(recipes))
        return recipes

    def analyze_extraction_quality(self, recipes: list[Recipe]) -> dict:
        """Analyze the quality and completeness of extractions."""
        if not recipes:
            return {"error": "No recipes to analyze"}

        total = len(recipes)

        # Count field completeness
        complete_fields = {
            "has_title": sum(1 for r in recipes if r.title and r.title != "unknown"),
            "has_ingredients": sum(1 for r in recipes if r.ingredients),
            "has_instructions": sum(1 for r in recipes if r.instructions),
            "has_proteins": sum(1 for r in recipes if r.proteins),
            "has_vegetables": sum(1 for r in recipes if r.vegetables),
            "has_cooking_methods": sum(1 for r in recipes if r.cooking_methods),
            "has_season": sum(
                1 for r in recipes if r.season and "unknown" not in r.season
            ),
            "has_occasion": sum(1 for r in recipes if r.occasion),
            "has_dietary_tags": sum(1 for r in recipes if r.dietary_tags),
        }

        # Calculate percentages
        completeness = {
            k: f"{(v / total) * 100:.1f}%" for k, v in complete_fields.items()
        }

        # Count unique values
        unique_counts = {
            "cuisines": len(set(r.cuisine_type for r in recipes)),
            "cooking_methods": len(
                set(method for r in recipes for method in r.cooking_methods),
            ),
            "proteins": len(set(protein for r in recipes for protein in r.proteins)),
            "vegetables": len(set(veg for r in recipes for veg in r.vegetables)),
        }

        return {
            "total_recipes": total,
            "field_completeness": completeness,
            "unique_values": unique_counts,
            "avg_ingredients_per_recipe": sum(len(r.ingredients) for r in recipes)
            / total,
            "avg_tags_per_recipe": sum(
                len(r.dietary_tags + r.style_tags + r.occasion) for r in recipes
            )
            / total,
        }

    def save_analysis(
        self,
        recipes: list[Recipe],
        output_path: Path = Path("analyzed_recipes.json"),
    ) -> None:
        """Save recipes with analysis metadata."""
        # Convert recipes to dict format
        recipes_data = [recipe.model_dump() for recipe in recipes]

        # Add analysis metadata
        analysis = self.analyze_extraction_quality(recipes)

        output_data = {
            "extraction_metadata": {
                "model_used": self.model,
                "extraction_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "total_recipes": len(recipes),
                "analysis": analysis,
            },
            "recipes": recipes_data,
        }

        output_path.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
        logger.info("Saved %d recipes to %s", len(recipes), output_path)

        # logger quality summary
        logger.info("\n📊 Extraction Quality Summary:")
        for field, percentage in analysis.get("field_completeness", {}).items():
            logger.info("  %s: %s", field, percentage)


def extract_recipes_comprehensively(
    api_key: str,
    posts: list[Media],
    model: str = "gpt-4.1",
) -> list[Recipe]:
    """Complete recipe extraction workflow.

    Args:
    ----
        api_key: OpenAI API key
        posts: Instagram posts to analyze
        model: Model to use ("gpt-4.1", "gpt-4o-mini", "gpt-5")

    Returns:
    -------
        List of comprehensive Recipe objects

    """
    extractor = MasterRecipeExtractor(api_key=api_key, model=model)

    logger.info("🚀 Starting comprehensive extraction for %d posts", len(posts))

    # Create and process batch
    batch_id = extractor.create_batch(posts)
    batch = extractor.wait_for_batch(batch_id)
    extractor.download_results(batch)

    # Parse results
    recipes = extractor.parse_results(posts)

    # Save with analysis
    extractor.save_analysis(recipes)

    logger.info("✅ Comprehensive extraction complete: %d recipes", len(recipes))
    return recipes
