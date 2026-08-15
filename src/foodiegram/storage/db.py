from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlmodel import Session, SQLModel, create_engine, select

from foodiegram.domain.planning import DEFAULT_TARGETS
from foodiegram.storage._tables import TargetRow

if TYPE_CHECKING:
    from sqlalchemy import Engine

_PROD_HOST_MARKERS = ("neon.tech", "neon.build")


def ensure_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC to a naive datetime read from storage.

    Every datetime we store is UTC; restore the marker at the read boundary
    rather than leak a naive value to the domain.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLModel engine for database_url with connection pre-ping."""
    return create_engine(database_url, pool_pre_ping=True)


def get_session(engine: Engine) -> Session:
    """Open a new session bound to engine."""
    return Session(engine)


def init_db(engine: Engine) -> None:
    """Create all tables and seed default targets when the table is empty."""
    SQLModel.metadata.create_all(engine)
    _ensure_schema_patches(engine)
    _seed_targets(engine)


def _ensure_schema_patches(engine: Engine) -> None:
    """Apply additive schema changes that create_all does not backfill."""
    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE recipes "
                "ADD COLUMN IF NOT EXISTS time_is_estimated "
                "BOOLEAN NOT NULL DEFAULT FALSE",
            ),
        )
        connection.execute(
            text("ALTER TABLE recipes ADD COLUMN IF NOT EXISTS caption_hash TEXT"),
        )
        connection.execute(
            text(
                "ALTER TABLE recipe_embeddings "
                "ADD COLUMN IF NOT EXISTS embedding_source_hash TEXT",
            ),
        )


def truncate_all_tables(engine: Engine) -> None:
    """Truncate every application table (test isolation only)."""
    table_names = ", ".join(
        table.name for table in reversed(SQLModel.metadata.sorted_tables)
    )
    with engine.begin() as connection:
        connection.execute(
            text(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE"),
        )


def _seed_targets(engine: Engine) -> None:
    """Insert DEFAULT_TARGETS if the targets table has no rows."""
    with get_session(engine) as session:
        if session.exec(select(TargetRow)).first() is not None:
            return
        for target in DEFAULT_TARGETS:
            session.add(
                TargetRow(
                    category=target.category.value,
                    min_servings=target.min_servings,
                    max_servings=target.max_servings,
                ),
            )
        session.commit()


def database_label(database_url: str) -> str:
    """Return host:port/database for human-readable CLI output."""
    parsed = make_url(database_url)
    host = parsed.host or "localhost"
    port = parsed.port or 5432
    database = parsed.database or ""
    return f"{host}:{port}/{database}"


def looks_like_prod(database_url: str) -> bool:
    """Return True when the URL host looks like a Neon production database."""
    host = (make_url(database_url).host or "").lower()
    return any(marker in host for marker in _PROD_HOST_MARKERS)
