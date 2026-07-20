from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlmodel import Session, SQLModel, create_engine, select

from foodiegram.domain.planning import DEFAULT_TARGETS
from foodiegram.storage._tables import TargetRow

if TYPE_CHECKING:
    from sqlalchemy import Engine

_SQLITE_PREFIX = "sqlite:///"


def ensure_utc(value: datetime | None) -> datetime | None:
    """Re-attach UTC to a naive datetime read from storage.

    SQLite cannot persist tzinfo; every datetime we store is UTC, so we restore
    the marker at the read boundary rather than leak a naive value to the domain.
    """
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _ensure_sqlite_parent(database_url: str) -> None:
    """Create the parent directory for a file-backed SQLite database if needed."""
    if not database_url.startswith(_SQLITE_PREFIX):
        return
    path = database_url.removeprefix(_SQLITE_PREFIX)
    if not path or path == ":memory:":
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLModel engine for database_url with connection pre-ping."""
    _ensure_sqlite_parent(database_url)
    connect_args = (
        {"check_same_thread": False} if database_url.startswith(_SQLITE_PREFIX) else {}
    )
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def get_session(engine: Engine) -> Session:
    """Open a new session bound to engine."""
    return Session(engine)


def init_db(engine: Engine) -> None:
    """Create all tables and seed default targets when the table is empty."""
    SQLModel.metadata.create_all(engine)
    _seed_targets(engine)


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
