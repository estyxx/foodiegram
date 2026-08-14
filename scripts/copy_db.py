"""Copy every table from the local SQLite backup into the working Postgres database.

Opens data/dispensa.db read-only (never writes to it) and copies into
DATABASE_URL. Run via:

    uv run python scripts/copy_db.py
    uv run python scripts/copy_db.py --yes
"""

import argparse
import logging
import sys
from pathlib import Path

from foodiegram.settings import Settings
from foodiegram.storage import maintenance
from foodiegram.storage.db import database_label

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the SQLite-to-Postgres copy."""
    parser = argparse.ArgumentParser(
        description="Copy data/dispensa.db into the working Postgres database.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=maintenance.SQLITE_SOURCE_DEFAULT,
        help="Read-only SQLite source file (default: data/dispensa.db)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Overwrite a non-empty Postgres target (truncate then copy).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()
    target_url = settings.database_url

    try:
        result = maintenance.copy_sqlite_to_postgres(
            sqlite_path=args.source,
            target_url=target_url,
            overwrite=args.yes,
        )
    except (FileNotFoundError, ValueError):
        logger.exception("Copy aborted")
        sys.exit(1)

    for line in maintenance.format_copy_report(result):
        logger.info(line)

    if not result.passed:
        logger.error(
            "Verification failed for %s",
            database_label(target_url),
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
