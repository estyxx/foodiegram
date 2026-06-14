"""Fetch or refresh cached Instagram posts.

Default mode: fetch only PKs from data/all_post_pks.json not yet in cache.
Refresh mode (--refresh): re-fetch every cached post to renew expired CDN URLs.

Run via:
    uv run python scripts/fetch_missing_posts.py
    uv run python scripts/fetch_missing_posts.py --refresh
    uv run python scripts/fetch_missing_posts.py \
        --pks data/all_post_pks.json --cache cookstagram-data/cache --delay 1.5
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from foodiegram.cache_manager import CacheManager
from foodiegram.instageram_extractor import InstagramExtractor
from foodiegram.settings import Settings

PKS_DEFAULT = Path("data/all_post_pks.json")
CACHE_DEFAULT = Path("cookstagram-data/cache")
DELAY_DEFAULT = 1.5

logger = logging.getLogger(__name__)


def main() -> None:
    """Fetch missing posts or refresh all cached posts to renew expired URLs."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch missing Instagram posts or refresh all cached ones. "
            "Uses gql (doc_id fallback) -> v1 -> v2 endpoint chain."
        ),
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch every cached post to renew expired CDN URLs.",
    )
    parser.add_argument(
        "--pks",
        type=Path,
        default=PKS_DEFAULT,
        metavar="PATH",
        help=f"JSON file with list of media PKs (default: {PKS_DEFAULT})",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=CACHE_DEFAULT,
        metavar="DIR",
        help=f"Cache directory (default: {CACHE_DEFAULT})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DELAY_DEFAULT,
        metavar="SECONDS",
        help=f"Delay between requests in seconds (default: {DELAY_DEFAULT})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    settings = Settings()
    extractor = InstagramExtractor(settings=settings, cache_dir=args.cache)

    if args.refresh:
        refreshed, failed = extractor.refresh_cached_posts(delay=args.delay)
        print("\nRefresh done.")
        print(f"  Refreshed : {refreshed}")
        print(f"  Failed    : {len(failed)}")
        if failed:
            print("\nFailed PKs:")
            for pk in failed:
                print(f"  {pk}")
        return

    if not args.pks.exists():
        logger.error("PKs file not found: %s", args.pks)
        sys.exit(1)

    pks: list[str] = json.loads(args.pks.read_text(encoding="utf-8"))
    logger.info("Loaded %d PKs from %s", len(pks), args.pks)

    cache_manager = CacheManager(cache_dir=args.cache)
    already_cached = sum(1 for pk in pks if cache_manager.get_post(pk) is not None)
    logger.info(
        "%d already cached, %d to fetch",
        already_cached,
        len(pks) - already_cached,
    )

    fetched, skipped, failed = extractor.fetch_posts_by_pks(pks, delay=args.delay)

    print("\nDone.")
    print(f"  Total PKs : {len(pks)}")
    print(f"  Fetched   : {fetched}")
    print(f"  Skipped   : {skipped}  (already cached)")
    print(f"  Failed    : {len(failed)}")

    if failed:
        print("\nFailed PKs:")
        for pk in failed:
            print(f"  {pk}")


if __name__ == "__main__":
    main()
