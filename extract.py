# extract.py - Improved version with proper caching
from __future__ import annotations

import json
import logging
from pathlib import Path

from foodiegram import env
from foodiegram.analyzer import RecipeAnalyzer
from foodiegram.cache_manager import CacheManager
from foodiegram.instageram_extractor import load_or_fetch_collection
from foodiegram.types import Recipe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_collection_recipes_sync(
    environment: env.Env,
    collection_id: int,
    limit: int = 100,
) -> list[Recipe]:
    """Synchronous recipe analysis using Pydantic AI."""
    cache = CacheManager()
    # Get the posts (cached or fresh)
    collection = load_or_fetch_collection(environment, collection_id, limit=limit)
    posts = [cache.get_post(post_id) for post_id in collection.post_pks[:20]]
    logger.info("Analyzing %s posts with Pydantic AI (sync)...", len(posts))

    # Initialize analyzer with Pydantic AI
    analyzer = RecipeAnalyzer(openai_api_key=environment.OPENAI_API_KEY)

    # Analyze all posts
    recipes = analyzer.analyze_posts_batch(posts)

    # Save results
    output_file = Path("analyzed_recipes.json")

    # Convert to dict for JSON serialization, handling enums
    recipes_data = [
        {
            **recipe.model_dump(),
            # Ensure enums are converted to strings
            "post_url": recipe.post_url,
            "dish_type": recipe.dish_type.value if recipe.dish_type else None,
            "meal_type": recipe.meal_type.value if recipe.meal_type else None,
            "cuisine_type": recipe.cuisine_type.value if recipe.cuisine_type else None,
            "difficulty": recipe.difficulty.value if recipe.difficulty else None,
        }
        for recipe in recipes
    ]

    output_file.write_text(json.dumps(recipes_data, indent=2, default=str))

    logger.info(f"Analysis complete! Results saved to {output_file}")
    logger.info(
        "Found %s recipes out of %s posts",
        len([r for r in recipes if r.is_recipe]),
        len(posts),
    )

    return recipes


# Example usage:
if __name__ == "__main__":
    # First run: fetches from Instagram and caches
    environment = env.Env.get_env()
    analyze_collection_recipes_sync(
        environment=environment,
        collection_id=environment.INSTAGRAM_COLLECTION_ID,
    )
