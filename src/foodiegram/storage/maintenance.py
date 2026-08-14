import logging
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import Integer, Table, delete, func, insert, select, text
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel

from foodiegram.storage.db import (
    _seed_targets,
    create_db_engine,
    database_label,
    looks_like_prod,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

SQLITE_SOURCE_DEFAULT = Path("data/dispensa.db")
_COPY_MISMATCH = "MISMATCH"
_COPY_PASS = "PASS"


@dataclass(frozen=True)
class CopyVerification:
    """Per-table row counts after a SQLite-to-Postgres copy."""

    table: str
    sqlite_rows: int
    postgres_rows: int

    @property
    def matches(self) -> bool:
        """Return True when source and target row counts agree."""
        return self.sqlite_rows == self.postgres_rows


@dataclass(frozen=True)
class CopyResult:
    """Outcome of copying every table from SQLite into Postgres."""

    verifications: tuple[CopyVerification, ...]

    @property
    def passed(self) -> bool:
        """Return True when every table's counts match."""
        return all(row.matches for row in self.verifications)


def ping_database(*, database_url: str) -> None:
    """Connect to database_url and run a trivial query."""
    engine = create_db_engine(database_url)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def create_tables(*, database_url: str) -> None:
    """Create any missing tables on the working database."""
    engine = create_db_engine(database_url)
    SQLModel.metadata.create_all(engine)
    _seed_targets(engine)


def reset_database(*, database_url: str) -> None:
    """Drop and recreate every table on the working database."""
    engine = create_db_engine(database_url)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    _seed_targets(engine)


def dump_database(*, database_url: str, output: Path) -> Path:
    """Back up database_url to a custom-format pg_dump file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["pg_dump", "-Fc", "-f", str(output), database_url],
        check=True,
    )
    return output


def restore_database(*, database_url: str, dump_path: Path) -> None:
    """Restore a custom-format pg_dump file into database_url."""
    subprocess.run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "-d",
            database_url,
            str(dump_path),
        ],
        check=True,
    )


def ensure_database(*, database_url: str) -> bool:
    """Create the Postgres database when it does not exist yet."""
    if looks_like_prod(database_url):
        label = database_label(database_url)
        msg = f"Refusing to create database on production-looking host: {label}"
        raise ValueError(msg)

    parsed = make_url(database_url)
    database_name = parsed.database
    if database_name is None:
        msg = "Database URL must include a database name"
        raise ValueError(msg)

    maintenance_url = parsed.set(database="postgres")
    engine = create_db_engine(
        maintenance_url.render_as_string(hide_password=False),
    )
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": database_name},
        ).scalar()
        if exists is not None:
            return False
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        return True


def _read_only_sqlite_url(path: Path) -> str:
    """Build a read-only SQLite URI for an on-disk database file."""
    resolved = path.resolve()
    return f"sqlite:///file:{resolved}?mode=ro&uri=true"


def _table_row_counts(engine: Engine) -> dict[str, int]:
    """Return per-table row counts for every mapped table."""
    counts: dict[str, int] = {}
    with engine.connect() as connection:
        for table in SQLModel.metadata.sorted_tables:
            counts[table.name] = connection.execute(
                select(func.count()).select_from(table),
            ).scalar_one()
    return counts


def _reset_sequences(connection: Connection) -> None:
    """Advance each Postgres identity sequence past the max copied primary key."""
    for table in SQLModel.metadata.sorted_tables:
        pk_columns = list(table.primary_key.columns)
        if len(pk_columns) != 1 or not isinstance(pk_columns[0].type, Integer):
            continue
        column = pk_columns[0]
        seq = connection.execute(
            text("SELECT pg_get_serial_sequence(:tbl, :col)"),
            {"tbl": table.name, "col": column.name},
        ).scalar()
        if seq is None:
            continue
        max_id = connection.execute(select(func.max(column))).scalar()
        if max_id is None:
            continue
        connection.execute(
            text("SELECT setval(:seq, :val, true)"),
            {"seq": seq, "val": max_id},
        )


def _copy_tables(
    *,
    source_connection: Connection,
    target_connection: Connection,
    tables: list[Table],
    overwrite: bool,
    non_empty: dict[str, int],
) -> None:
    """Insert every mapped table from source into target inside one transaction."""
    if overwrite and non_empty:
        for table in reversed(tables):
            target_connection.execute(delete(table))

    for table in tables:
        columns = [column.name for column in table.columns]
        rows = [
            dict(zip(columns, row, strict=True))
            for row in source_connection.execute(select(table))
        ]
        if rows:
            target_connection.execute(insert(table), rows)


def _verify_copy_counts(
    *,
    target_connection: Connection,
    source_counts: dict[str, int],
    tables: list[Table],
) -> list[CopyVerification]:
    """Compare per-table row counts and raise when any table mismatches."""
    verifications: list[CopyVerification] = []
    for table in tables:
        sqlite_rows = source_counts.get(table.name, 0)
        postgres_rows = target_connection.execute(
            select(func.count()).select_from(table),
        ).scalar_one()
        verifications.append(
            CopyVerification(
                table=table.name,
                sqlite_rows=sqlite_rows,
                postgres_rows=postgres_rows,
            ),
        )
        if sqlite_rows != postgres_rows:
            msg = (
                f"Row-count mismatch on {table.name}: "
                f"sqlite={sqlite_rows} postgres={postgres_rows}"
            )
            raise ValueError(msg)
    return verifications


def copy_sqlite_to_postgres(
    *,
    sqlite_path: Path,
    target_url: str,
    overwrite: bool,
) -> CopyResult:
    """Copy every table from a read-only SQLite file into Postgres."""
    if looks_like_prod(target_url):
        label = database_label(target_url)
        msg = f"Refusing to copy into a production-looking database: {label}"
        raise ValueError(msg)

    if not sqlite_path.is_file():
        msg = f"Source SQLite database not found: {sqlite_path}"
        raise FileNotFoundError(msg)

    source_url = _read_only_sqlite_url(sqlite_path)
    source_engine = create_db_engine(source_url)
    target_engine = create_db_engine(target_url)
    SQLModel.metadata.create_all(target_engine)

    target_counts_before = _table_row_counts(target_engine)
    non_empty = {
        name: count for name, count in target_counts_before.items() if count > 0
    }
    if non_empty and not overwrite:
        msg = (
            f"Target already has data ({non_empty}); pass --yes to overwrite "
            f"({database_label(target_url)})"
        )
        raise ValueError(msg)

    source_counts = _table_row_counts(source_engine)
    tables = list(SQLModel.metadata.sorted_tables)

    try:
        with (
            source_engine.connect() as source_connection,
            target_engine.begin() as target_connection,
        ):
            _copy_tables(
                source_connection=source_connection,
                target_connection=target_connection,
                tables=tables,
                overwrite=overwrite,
                non_empty=non_empty,
            )
            _reset_sequences(target_connection)
            verifications = _verify_copy_counts(
                target_connection=target_connection,
                source_counts=source_counts,
                tables=tables,
            )
    except Exception:
        logger.exception(
            "Copy failed; target rolled back to pre-copy state (%s)",
            database_label(target_url),
        )
        raise

    return CopyResult(verifications=tuple(verifications))


def default_dump_path(*, backups_dir: Path = Path("backups")) -> Path:
    """Return a timestamped pg_dump path under backups/."""
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    return backups_dir / f"dispensa-{stamp}.dump"


def format_copy_report(result: CopyResult) -> Sequence[str]:
    """Return human-readable verification lines for a copy result."""
    header = f"{'table':<16} | {'sqlite_rows':>11} | {'postgres_rows':>13}"
    lines = [header, "-" * len(header)]
    lines.extend(
        f"{row.table:<16} | {row.sqlite_rows:>11} | {row.postgres_rows:>13}"
        for row in result.verifications
    )
    status = _COPY_PASS if result.passed else _COPY_MISMATCH
    lines.append(status)
    return lines


def refuse_destructive_on_prod(*, database_url: str, action: str) -> None:
    """Raise when a destructive CLI action targets a production-looking host."""
    if looks_like_prod(database_url):
        msg = (
            f"Refusing to {action} a production-looking database: "
            f"{database_label(database_url)}"
        )
        raise ValueError(msg)


def require_confirmation(*, confirmed: bool, action: str, database_url: str) -> None:
    """Raise when a destructive action was requested without --yes."""
    if confirmed:
        return
    msg = f"Refusing to {action} without --yes ({database_label(database_url)})"
    raise ValueError(msg)
