"""One-shot migration: drop removed user-state keys from stored recipe JSON.

`user_notes` and `is_favorite` were removed from Recipe (they move to user_state
in a later phase). Legacy files still carry them, so `extra="forbid"` rejects
every file on read. This script strips those keys and rewrites each file through
the current Recipe model, backfilling the new source/edited_fields/archived
defaults. Safe to re-run.

Run via: uv run scripts/migrate_drop_user_state_fields.py
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from foodiegram.domain.models import Recipe
from foodiegram.settings import Settings

_REMOVED_KEYS = ("user_notes", "is_favorite")

logger = logging.getLogger(__name__)


def _migrate_file(path: Path) -> bool:
    """Rewrite one recipe file without the removed keys; return True if changed."""
    raw: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    removed = [key for key in _REMOVED_KEYS if key in raw]
    if not removed:
        return False

    for key in removed:
        del raw[key]

    recipe = Recipe.model_validate(raw)
    path.write_text(recipe.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Migrated %s (dropped %s)", path.name, ", ".join(removed))
    return True


def main() -> None:
    """Run the migration over every recipe file in the data directory."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Drop removed user-state keys from stored recipe JSON.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Settings().data_dir,
        metavar="DIR",
        help="Recipe directory (default: from settings)",
    )
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    if not data_dir.exists():
        logger.error("Data directory not found: %s", data_dir)
        sys.exit(1)

    migrated = 0
    unchanged = 0
    errors = 0

    for path in sorted(data_dir.glob("*.json")):
        try:
            if _migrate_file(path):
                migrated += 1
            else:
                unchanged += 1
        except (json.JSONDecodeError, ValueError, OSError):
            logger.exception("Failed to migrate %s", path.name)
            errors += 1

    print(
        f"\nMigration complete: {migrated} migrated, "
        f"{unchanged} unchanged, {errors} errors",
    )


if __name__ == "__main__":
    main()
