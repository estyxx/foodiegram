"""Copy every table from a local SQLite database into another database (e.g. Neon).

Creates the schema on the target, copies each table in FK-dependency order, and
resets Postgres identity sequences so future inserts don't collide with copied
integer primary keys.

Run via:
    DATABASE_URL unset here on purpose — pass the target explicitly:
    uv run python scripts/copy_db.py --target "postgresql://…neon…?sslmode=require"
"""

import argparse
import logging
import sys
from pathlib import Path

from sqlalchemy import Integer, delete, func, insert, select, text
from sqlmodel import SQLModel

from foodiegram.storage.db import create_db_engine

SOURCE_DEFAULT = "sqlite:///data/dispensa.db"
_SQLITE_PREFIX = "sqlite:///"

logger = logging.getLogger(__name__)


def _sqlite_file_missing(url: str) -> bool:
    """Return True when url is a file-backed SQLite DB that does not exist."""
    if not url.startswith(_SQLITE_PREFIX):
        return False
    path = url.removeprefix(_SQLITE_PREFIX)
    return path not in ("", ":memory:") and not Path(path).exists()


def _target_row_counts(target_url: str) -> dict[str, int]:
    """Create the schema if absent, then return per-table target row counts."""
    engine = create_db_engine(target_url)
    SQLModel.metadata.create_all(engine)
    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for table in SQLModel.metadata.sorted_tables:
            counts[table.name] = conn.execute(
                select(func.count()).select_from(table),
            ).scalar_one()
    return counts


def _reset_sequences(target_url: str) -> None:
    """Advance each Postgres identity sequence past the max copied primary key."""
    engine = create_db_engine(target_url)
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            pk_cols = list(table.primary_key.columns)
            if len(pk_cols) != 1 or not isinstance(pk_cols[0].type, Integer):
                continue
            col = pk_cols[0]
            seq = conn.execute(
                text("SELECT pg_get_serial_sequence(:tbl, :col)"),
                {"tbl": table.name, "col": col.name},
            ).scalar()
            if seq is None:
                continue
            max_id = conn.execute(select(func.max(col))).scalar()
            if max_id is None:
                continue
            conn.execute(
                text("SELECT setval(:seq, :val, true)"),
                {"seq": seq, "val": max_id},
            )
            logger.info("Reset sequence %s to %s", seq, max_id)


def copy_all(*, source_url: str, target_url: str, truncate: bool) -> dict[str, int]:
    """Copy every table from source to target; return per-table copied counts."""
    source = create_db_engine(source_url)
    target = create_db_engine(target_url)
    SQLModel.metadata.create_all(target)

    copied: dict[str, int] = {}
    tables = list(SQLModel.metadata.sorted_tables)
    with source.connect() as src, target.begin() as dst:
        if truncate:
            for table in reversed(tables):
                dst.execute(delete(table))
        for table in tables:
            columns = [column.name for column in table.columns]
            rows = [
                dict(zip(columns, row, strict=True))
                for row in src.execute(select(table))
            ]
            copied[table.name] = len(rows)
            if rows:
                dst.execute(insert(table), rows)
    return copied


def main() -> None:
    """Run the SQLite-to-target copy."""
    parser = argparse.ArgumentParser(
        description="Copy a local SQLite database into a target database (e.g. Neon).",
    )
    parser.add_argument(
        "--source",
        default=SOURCE_DEFAULT,
        metavar="URL",
        help=f"Source database URL (default: {SOURCE_DEFAULT})",
    )
    parser.add_argument(
        "--target",
        required=True,
        metavar="URL",
        help="Target database URL (the Neon postgresql:// connection string).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing target rows before copying (use to re-run a copy).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report source row counts without writing to the target.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if _sqlite_file_missing(args.source):
        logger.error("Source SQLite database not found: %s", args.source)
        sys.exit(1)

    if args.dry_run:
        source = create_db_engine(args.source)
        with source.connect() as conn:
            for table in SQLModel.metadata.sorted_tables:
                count = conn.execute(
                    select(func.count()).select_from(table),
                ).scalar_one()
                logger.info("%-16s %6d rows", table.name, count)
        return

    if not args.truncate:
        existing = _target_row_counts(args.target)
        non_empty = {name: n for name, n in existing.items() if n > 0}
        if non_empty:
            logger.error(
                "Target already has data (%s); pass --truncate to overwrite.",
                non_empty,
            )
            sys.exit(1)

    copied = copy_all(
        source_url=args.source,
        target_url=args.target,
        truncate=args.truncate,
    )
    _reset_sequences(args.target)

    total = sum(copied.values())
    for name, count in copied.items():
        logger.info("Copied %-16s %6d rows", name, count)
    logger.info("Done: %d rows across %d tables", total, len(copied))


if __name__ == "__main__":
    main()
