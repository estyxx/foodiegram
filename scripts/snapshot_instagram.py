"""Snapshot saved Instagram posts to a local IGbulkDL-shaped JSON file.

Stage A only: touches Instagram and the filesystem. Does not use the DB,
Cloudinary, or OpenAI. Stage B reconciles against the written snapshot offline.

Run via:
    uv run python scripts/snapshot_instagram.py
    uv run python scripts/snapshot_instagram.py --full
    uv run python scripts/snapshot_instagram.py --output data/food.json
"""

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from foodiegram.domain.errors import ConfigurationError
from foodiegram.instagram import InstagramExtractor
from foodiegram.instagram.snapshot import (
    collect_saved_posts,
    default_output_path,
    write_snapshot,
)
from foodiegram.settings import Settings

_DEFAULT_CACHE_DIR = Path("cache")

logger = logging.getLogger(__name__)


def _resolve_collection_id(*, settings: Settings, override: str | None) -> str:
    """Return the collection id from CLI override or settings."""
    collection_id = override or settings.instagram_collection_id
    if not collection_id:
        msg = (
            "INSTAGRAM_COLLECTION_ID is required (or pass --collection-id). "
            "Set it in .env to the numeric id of your saved-posts collection."
        )
        raise ConfigurationError(msg)
    return collection_id


def main() -> None:
    """Pull saved posts and write an IGbulkDL-shaped JSON snapshot."""
    parser = argparse.ArgumentParser(
        description=(
            "Snapshot saved Instagram posts to a local JSON file "
            "(IGbulkDL food.json shape)."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="PATH",
        help="Destination JSON file (default: data/ig_snapshot-<timestamp>.json)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help=(
            "Re-pull the entire collection. Heavier on the account; "
            "default incremental mode stops at already-cached shortcodes."
        ),
    )
    parser.add_argument(
        "--collection-id",
        default=None,
        metavar="ID",
        help="Saved collection id (default: INSTAGRAM_COLLECTION_ID from .env)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=_DEFAULT_CACHE_DIR,
        metavar="DIR",
        help=f"Instagram cache directory (default: {_DEFAULT_CACHE_DIR})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    captured_at = datetime.now(tz=UTC)
    output_path = args.output or default_output_path(captured_at=captured_at)
    incremental = not args.full

    settings = Settings()
    settings.require_instagram()
    collection_id = _resolve_collection_id(
        settings=settings,
        override=args.collection_id,
    )

    if args.full:
        logger.warning(
            "Full snapshot requested — paging the entire collection is heavier "
            "on the Instagram account than incremental mode.",
        )

    extractor = InstagramExtractor(settings=settings, cache_dir=args.cache_dir)
    result = collect_saved_posts(
        extractor=extractor,
        collection_id=collection_id,
        incremental=incremental,
    )

    write_snapshot(
        output_path=output_path,
        items=result.items,
        captured_at=captured_at,
    )

    print(f"{result.fetched}  {result.new_since_last}  {output_path}")

    if result.partial:
        logger.error(
            "Partial snapshot written after an API failure: %s",
            result.error_message,
        )
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except ConfigurationError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
