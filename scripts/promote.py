"""Promote the latest extraction at a prompt version into recipes.

Honours DATABASE_URL (default sqlite:///data/dispensa.db). Dry-run by default;
pass --apply to write. User-edited fields are never overwritten. Run via:
uv run scripts/promote.py --version 2 [--batch ID] [--apply]
"""

import argparse
import logging

from foodiegram.app.promotion import promote_version
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.recipes_db import RecipeRepository

_MAX_LISTED = 40


def main() -> None:
    """Promote a prompt version across the recipe library."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Promote extractions into recipes.")
    parser.add_argument("--version", required=True, help="Prompt version to promote")
    parser.add_argument("--batch", default=None, help="Restrict to one batch id")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes (default: dry-run, prints what would change)",
    )
    args = parser.parse_args()

    settings = Settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)

    report = promote_version(
        recipes=RecipeRepository(engine),
        extractions=ExtractionRepository(engine),
        version=args.version,
        batch_id=args.batch,
        dry_run=not args.apply,
    )

    for change in report.changes[:_MAX_LISTED]:
        if change.diffs:
            fields = ", ".join(diff.field for diff in change.diffs)
            print(f"  {change.code}: {fields}")
    if len(report.changes) > _MAX_LISTED:
        print(f"  ... and {len(report.changes) - _MAX_LISTED} more")

    mode = "DRY-RUN" if report.dry_run else "APPLIED"
    print(
        f"\n[{mode}] version {report.version}: "
        f"{report.considered} considered, {report.changed} would change"
        f"{f', {report.promoted} promoted' if not report.dry_run else ''}, "
        f"{report.total_skipped_fields} fields skipped (user-edited), "
        f"{report.missing_recipe} extractions without a recipe",
    )


if __name__ == "__main__":
    main()
