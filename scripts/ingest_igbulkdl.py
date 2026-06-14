"""Ingest one or more IGbulkDL JSON log files into RecipeRepository.

For each item where status == "ok":
  - If the recipe already exists: back-fill caption and/or thumbnail_url only
    when those fields are currently null/empty (never touch AI-extracted data).
  - If the recipe is new: create a minimal stub with the caption and a public
    thumbnail URL, ready for later AI extraction.

CLI:
    python scripts/ingest_igbulkdl.py data/food.json [data/more.json ...]
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from foodiegram.domain.errors import StorageError
from foodiegram.domain.models import Recipe
from foodiegram.repository import RecipeRepository

DATA_DIR = Path("data/recipes")

logger = logging.getLogger(__name__)


@dataclass
class _Item:
    """Parsed representation of one IGbulkDL log entry."""

    shortcode: str
    pk: str
    caption: str | None
    title: str
    thumbnail_url: str


@dataclass
class _Stats:
    """Running totals for the summary line."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _thumbnail_url(shortcode: str) -> str:
    """Return the public Instagram thumbnail endpoint for a shortcode."""
    return f"https://www.instagram.com/p/{shortcode}/media/?size=l"


def _parse_items(log_path: Path) -> list[_Item]:
    """Parse IGbulkDL JSON log file; return only status == 'ok' entries."""
    raw = json.loads(log_path.read_text(encoding="utf-8"))
    items: list[_Item] = []
    for entry in raw.get("items", []):
        if entry.get("status") not in ("ok", "dry_run"):
            continue
        shortcode: str = entry["shortcode"]
        items.append(
            _Item(
                shortcode=shortcode,
                pk=str(entry.get("username", "")),
                caption=entry.get("caption") or None,
                title=str(entry.get("title", "")),
                thumbnail_url=_thumbnail_url(shortcode),
            ),
        )
    return items


def _process_item(item: _Item, repo: RecipeRepository, stats: _Stats) -> None:
    """Create or update a recipe for one IGbulkDL item."""
    try:
        existing = repo.get(item.shortcode)
    except StorageError as exc:
        logger.exception("Failed to read %s", item.shortcode)
        stats.errors.append(f"{item.shortcode}: {exc}")
        return

    if existing is not None:
        updates: dict[str, object] = {}
        if not existing.caption and item.caption:
            updates["caption"] = item.caption
        if not existing.thumbnail_url:
            updates["thumbnail_url"] = item.thumbnail_url
        if not updates:
            stats.skipped += 1
            return
        updated = existing.model_copy(update=updates)
        try:
            repo.save(updated)
        except StorageError as exc:
            logger.exception("Failed to save update for %s", item.shortcode)
            stats.errors.append(f"{item.shortcode}: {exc}")
            return
        stats.updated += 1
        logger.info("Updated %s (fields: %s)", item.shortcode, list(updates))
        return

    # Recipe.title is required; fall back to the IGbulkDL title field.
    recipe = Recipe(
        code=item.shortcode,
        pk=item.pk,
        post_url=f"https://instagram.com/p/{item.shortcode}/",
        caption=item.caption,
        title=item.title,
        ingredients=[],
        instructions=[],
        thumbnail_url=item.thumbnail_url,
        # Recipe has no "source" field; model_used carries provenance.
        model_used="imported",
    )
    try:
        repo.save(recipe)
    except StorageError as exc:
        logger.exception("Failed to save new recipe %s", item.shortcode)
        stats.errors.append(f"{item.shortcode}: {exc}")
        return
    stats.created += 1
    logger.info("Created %s", item.shortcode)


def main() -> None:
    """Run the ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest IGbulkDL JSON log files into RecipeRepository.",
    )
    parser.add_argument(
        "log_files",
        nargs="+",
        type=Path,
        metavar="FILE",
        help="One or more IGbulkDL JSON log files (each with an 'items' array)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DATA_DIR,
        metavar="DIR",
        help=f"Recipe output directory (default: {DATA_DIR})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    repo = RecipeRepository(args.out)
    stats = _Stats()

    for log_path in args.log_files:
        if not log_path.exists():
            logger.error("File not found: %s", log_path)
            stats.errors.append(f"{log_path}: file not found")
            continue
        logger.info("Reading %s", log_path)
        try:
            items = _parse_items(log_path)
        except (json.JSONDecodeError, KeyError) as exc:
            logger.exception("Cannot parse %s", log_path)
            stats.errors.append(f"{log_path}: {exc}")
            continue
        for item in items:
            _process_item(item, repo, stats)

    print("\nIngestion complete")
    print(f"  New recipes created : {stats.created}")
    print(f"  Existing updated    : {stats.updated}")
    print(f"  Skipped (no change) : {stats.skipped}")
    print(f"  Errors              : {len(stats.errors)}")
    if stats.errors:
        print("\nErrors:")
        for msg in stats.errors:
            print(f"  {msg}")

    if stats.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
