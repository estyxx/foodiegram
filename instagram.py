import logging
from pathlib import Path

from foodiegram import env
from foodiegram.instageram_extractor import InstagramExtractor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def read_collection_ids_from_file(file_path: str) -> list[int]:
    """Read collection IDs from the collections_food.txt file."""
    collection_ids = []
    try:
        with Path(file_path).open(encoding="utf-8") as file:
            for file_line in file:
                stripped_line = file_line.strip()
                if stripped_line:  # Skip empty lines
                    # Extract the first column (collection ID)
                    parts = stripped_line.split()
                    if parts:
                        collection_id = int(parts[0])
                        collection_ids.append(collection_id)
    except FileNotFoundError:
        logger.exception("File %s not found", file_path)
    except (ValueError, OSError):
        logger.exception("Error reading file %s", file_path)

    return collection_ids


if __name__ == "__main__":
    environment = env.Env.get_env()

    extractor = InstagramExtractor(
        username=environment.INSTAGRAM_USERNAME,
        password=environment.INSTAGRAM_PASSWORD,
    )

    # Read collection IDs from the file
    collections_file = "cache/collections/collections_food.txt"
    collection_ids = read_collection_ids_from_file(collections_file)

    logger.info("Found %d collections to process", len(collection_ids))

    # Fetch posts for each collection
    for collection_id in collection_ids:
        logger.info("Fetching posts for collection ID: %d", collection_id)
        try:
            # Use a very high limit to get all posts
            posts = extractor.fetch_collection_posts(
                collection_id=collection_id,
                limit=10000,  # Very high limit to get all posts
            )
            logger.info(
                "Successfully fetched %d posts for collection %d",
                len(posts),
                collection_id,
            )

            # Save posts to cache
            if posts:
                extractor.cache_manager.save_collection(collection_id, posts)
                logger.info(
                    "Saved %d posts to cache for collection %d",
                    len(posts),
                    collection_id,
                )

        except (ValueError, ConnectionError, TimeoutError):
            logger.exception("Error fetching posts for collection %d", collection_id)

    logger.info("Finished processing all collections")
