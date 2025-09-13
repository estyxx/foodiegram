import json
import logging
from pathlib import Path

from foodiegram import env
from foodiegram.analyzer import RecipeExtractorRealtime
from foodiegram.cache_manager import CacheManager
from foodiegram.instageram_extractor import load_or_fetch_collection
from foodiegram.recipe_extractor import extract_recipes_comprehensively

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_recipe_realtime(
    environment: env.Env,
    collection_id: int,
    limit: int = 100,
) -> None:
    """Extract recipes using simple approach."""
    # Get posts
    cache = CacheManager()
    collection = load_or_fetch_collection(environment, collection_id, limit=limit)
    posts = [cache.get_post(post_id) for post_id in collection.post_pks[:limit]]

    logger.info("Processing %d posts", len(posts))

    # Run simple extraction
    recipes = RecipeExtractorRealtime(
        api_key=environment.OPENAI_API_KEY,
    ).analyze_posts(posts)

    output_file = Path("data/extracted_recipes_realtime.json")
    recipes_data = [recipe.model_dump() for recipe in recipes]
    output_file.write_text(json.dumps(recipes_data, indent=2))
    logger.info("Found %d recipes", len(recipes))


def extract_recipes_batch_api(
    environment: env.Env,
    collection_id: int,
    limit: int = 100,
) -> None:
    """Extract recipes using comprehensive approach."""
    # Get posts
    cache = CacheManager()
    collection = load_or_fetch_collection(environment, collection_id, limit=limit)
    posts = [cache.get_post(post_id) for post_id in collection.post_pks[:limit]]

    logger.info("Processing %d posts", len(posts))

    # Run comprehensive extraction
    recipes = extract_recipes_comprehensively(
        api_key=environment.OPENAI_API_KEY,
        posts=posts,
    )

    output_file = Path("data/extracted_recipes.json")
    recipes_data = [recipe.model_dump() for recipe in recipes]
    output_file.write_text(json.dumps(recipes_data, indent=2))
    logger.info("Found %d recipes", len(recipes))


if __name__ == "__main__":
    environment = env.Env.get_env()
    extract_recipes_batch_api(
        environment=environment,
        collection_id=environment.INSTAGRAM_COLLECTION_ID,
        limit=5,
    )

    # extract_recipe_realtime(
    #     environment=environment,
    #     collection_id=environment.INSTAGRAM_COLLECTION_ID,
    #     limit=4,
    # )
