from collections.abc import Generator

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Engine, text
from sqlmodel import Session, SQLModel

from dispensa.settings import Settings
from dispensa.storage.db import create_db_engine
from dispensa.storage.maintenance import ensure_database
from dispensa.storage.migrations_runner import (
    current_revision,
    stamp_head,
    upgrade_to_head,
)


def _alembic_database_url() -> str:
    """Return a third test database, emptied and rebuilt from migrations only."""
    base = Settings(_env_file=None).database_url_test
    prefix, _, _name = base.rpartition("/")
    return f"{prefix}/dispensa_test_alembic"


@pytest.fixture(scope="session")
def migrated_engine() -> Generator[Engine]:
    """Build an empty database and bring it up to head with Alembic alone."""
    url = _alembic_database_url()
    ensure_database(database_url=url)
    engine = create_db_engine(url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    upgrade_to_head(url)
    yield engine
    engine.dispose()


def test_migrations_build_the_models_schema(migrated_engine: Engine) -> None:
    """A database built by migrations matches the models (so it matches create_all).

    The acceptance for D38/18.1: an Alembic-built schema has no diff against
    SQLModel.metadata, which is exactly what create_all builds from.
    """
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={"compare_type": True},
        )
        diffs = compare_metadata(context, SQLModel.metadata)

    assert diffs == [], f"migrations drifted from the models: {diffs}"


def test_head_is_recorded_after_upgrade(migrated_engine: Engine) -> None:
    """Upgrading stamps a concrete revision, so the DB is Alembic-managed."""
    assert current_revision(migrated_engine) is not None


def test_stamp_head_adopts_an_existing_schema(migrated_engine: Engine) -> None:
    """stamp_head sets the version without running DDL (the Neon adoption path)."""
    with Session(migrated_engine) as session:
        session.execute(text("DELETE FROM alembic_version"))
        session.commit()
    assert current_revision(migrated_engine) is None

    stamp_head(_alembic_database_url())
    assert current_revision(migrated_engine) is not None
