"""Backfill Recipe.author_username from the local Instagram post cache.

Recipe pk was not reliably captured, so posts are matched by shortcode (the
Media.code, which is the recipe key). Run before copying the DB to prod:
    uv run python scripts/backfill_authors.py [--dry-run] [--force]
"""

import argparse
import logging
from pathlib import Path

from instagrapi.types import Media

from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine
from foodiegram.storage.recipes_db import RecipeRepository

_DEFAULT_CACHE_DIR = Path("cache")

logger = logging.getLogger(__name__)


def _load_author_index(posts_dir: Path) -> dict[str, str]:
    """Map Instagram shortcode to author handle from cached post files."""
    index: dict[str, str] = {}
    for path in posts_dir.glob("*.json"):
        try:
            media = Media.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            logger.warning("Skipping unreadable cache file %s", path.name)
            continue
        user = media.user
        username = user.username if user else None
        if media.code and username:
            index[str(media.code)] = str(username)
    return index


def main() -> None:
    """Run the author backfill against the configured database."""
    parser = argparse.ArgumentParser(
        description="Backfill Recipe.author_username from the Instagram post cache.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_DEFAULT_CACHE_DIR,
        metavar="DIR",
        help=f"Instagram cache directory (default: {_DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an author_username that is already set.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    index = _load_author_index(args.cache_dir / "posts")
    logger.info("Loaded %d authors from cache", len(index))

    settings = Settings()
    repo = RecipeRepository(create_db_engine(settings.database_url))

    updated = 0
    skipped = 0
    missing = 0
    for recipe in repo.list_all():
        if recipe.author_username and not args.force:
            skipped += 1
            continue
        author = index.get(recipe.code)
        if author is None:
            missing += 1
            continue
        if author == recipe.author_username:
            skipped += 1
            continue
        logger.info("%s -> @%s", recipe.code, author)
        if not args.dry_run:
            repo.save(recipe.model_copy(update={"author_username": author}))
        updated += 1

    logger.info("Done: updated=%d skipped=%d missing=%d", updated, skipped, missing)


if __name__ == "__main__":
    main()
