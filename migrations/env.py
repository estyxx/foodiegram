from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

import dispensa.storage._tables  # noqa: F401  # register every table on the metadata
from dispensa.settings import Settings
from dispensa.storage.db import create_db_engine

# The Alembic Config object, providing access to the values in alembic.ini.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel collects every table=True class on one metadata; autogenerate diffs
# against it. Importing _tables above is what populates it.
target_metadata = SQLModel.metadata


def _database_url() -> str:
    """Use the url the caller set on the config, else the app's DATABASE_URL."""
    return config.get_main_option("sqlalchemy.url") or Settings().database_url


def run_migrations_offline() -> None:
    """Run migrations without a DBAPI, emitting SQL for review."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live connection."""
    connectable = create_db_engine(_database_url())
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
