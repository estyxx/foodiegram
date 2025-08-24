import json
import logging
from pathlib import Path

from better.master_recipe_extractor import extract_recipes_comprehensively
from better.recipe_analyzer import RecipeExtractor

from foodiegram import env
from foodiegram.cache_manager import CacheManager
from foodiegram.instageram_extractor import load_or_fetch_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_recipes(environment: env.Env, collection_id: int, limit: int = 100) -> None:
    """Extract recipes using simplified approach."""
    # Get posts
    cache = CacheManager()
    collection = load_or_fetch_collection(environment, collection_id, limit=limit)
    posts = [cache.get_post(post_id) for post_id in collection.post_pks[:limit]]

    logger.info("Processing %d posts", len(posts))

    # Create extractor and run batch
    extractor = RecipeExtractor(api_key=environment.OPENAI_API_KEY)

    batch_id = extractor.create_batch(posts)
    logger.info("Created batch: %s", batch_id)

    batch = extractor.wait_for_batch(batch_id)
    logger.info("Batch completed: %s", batch.status)

    extractor.download_results(batch)
    recipes = extractor.parse_results(posts)

    # Save final results
    output_file = Path("analyzed_recipes.json")
    recipes_data = [recipe.model_dump() for recipe in recipes]
    output_file.write_text(json.dumps(recipes_data, indent=2))

    logger.info("Saved %d recipes to %s", len(recipes), output_file)
    logger.info("Found %d actual recipes", sum(1 for r in recipes if r.is_recipe))


def analyze(environment: env.Env, collection_id: int, limit: int = 100) -> None:
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

    logger.info("Found %d recipes", len(recipes))


if __name__ == "__main__":
    environment = env.Env.get_env()
    # extract_recipes(
    #     environment=environment,
    #     collection_id=environment.INSTAGRAM_COLLECTION_ID,
    #     limit=2,
    # )

    analyze(
        environment=environment,
        collection_id=environment.INSTAGRAM_COLLECTION_ID,
        limit=4,
    )
