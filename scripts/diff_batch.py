"""Compare extractions between two prompt versions.

Answers "I changed the prompt/model — what actually changed?". Honours
DATABASE_URL (default sqlite:///data/dispensa.db). Run via:
uv run scripts/diff_batch.py --from-version 1 --to-version 2 [--summary] \
    [--field dish_type] [--code ABC]
"""

import argparse
import logging

from foodiegram.app.diff_batch import diff_versions
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.extractions_db import ExtractionRepository

_MAX_LISTED = 60


def main() -> None:
    """Print a per-recipe or aggregate diff between two prompt versions."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="Diff extractions across versions.")
    parser.add_argument("--from-version", required=True, dest="from_version")
    parser.add_argument("--to-version", required=True, dest="to_version")
    parser.add_argument("--summary", action="store_true", help="Only field aggregates")
    parser.add_argument("--field", default=None, help="Restrict to one field")
    parser.add_argument("--code", default=None, help="Restrict to one recipe")
    args = parser.parse_args()

    settings = Settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)

    report = diff_versions(
        extractions=ExtractionRepository(engine),
        from_version=args.from_version,
        to_version=args.to_version,
        field=args.field,
        code=args.code,
    )

    if not args.summary:
        for change in report.changes[:_MAX_LISTED]:
            fields = ", ".join(diff.field for diff in change.diffs)
            print(f"  {change.code}: {fields}")
        if len(report.changes) > _MAX_LISTED:
            print(f"  ... and {len(report.changes) - _MAX_LISTED} more")

    print(
        f"\nv{report.from_version} -> v{report.to_version}: "
        f"{report.compared} compared, {report.changed} changed",
    )
    for field, count in sorted(
        report.field_counts.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        print(f"  {field}: {count}")


if __name__ == "__main__":
    main()
