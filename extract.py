# extract.py - Improved version with proper caching
from __future__ import annotations

import json
import logging
from pathlib import Path

from cookstagram import cache_manager, env
from cookstagram.analyzer import RecipeAnalyzer
from cookstagram.instageram_extractor import load_or_fetch_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_collection_recipes(
    environment: env.Env,
    collection_id: int,
    limit: int = 100,
) -> None:
    """Extract and analyze recipes from an Instagram collection."""
    # Get the posts (cached or fresh)
    collection = load_or_fetch_collection(
        environment=environment,
        collection_id=collection_id,
        limit=limit,
    )
    cache = cache_manager.CacheManager()
    # Initialize analyzer
    analyzer = RecipeAnalyzer(openai_api_key=environment.OPENAI_API_KEY)

    posts = [cache.get_post(post_id) for post_id in collection.post_pks[:20]]

    # Analyze all posts
    recipes = analyzer.analyze_posts_batch(posts)

    # Save results
    output_file = Path("analyzed_recipes.json")
    recipes_data = [recipe.model_dump() for recipe in recipes]
    output_file.write_text(json.dumps(recipes_data, indent=2, default=str))

    logger.info(f"Analysis complete! Results saved to {output_file}")
    logger.info(
        f"Found {len([r for r in recipes if r.is_recipe])} recipes out of {len(posts)} posts",
    )


# Example usage:
if __name__ == "__main__":
    # First run: fetches from Instagram and caches
    environment = env.Env.get_env()
    analyze_collection_recipes(
        environment=environment,
        collection_id=environment.INSTAGRAM_COLLECTION_ID,
        limit=1000,
    )

    # Subsequent runs: uses cache
    # recipes = analyze_collection_recipes(collection_id=17854976980356429, limit=50)
