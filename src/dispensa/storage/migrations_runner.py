import logging
from pathlib import Path
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext

if TYPE_CHECKING:
    from sqlalchemy import Engine

logger = logging.getLogger(__name__)

# alembic.ini and the migrations/ tree live at the repo root, three levels above
# this package (src/dispensa/storage/ -> repo root).
_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _ROOT / "alembic.ini"
_MIGRATIONS = _ROOT / "migrations"


def _config(url: str) -> Config:
    """Build an Alembic config bound to our migrations tree and this url."""
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("script_location", str(_MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def current_revision(engine: Engine) -> str | None:
    """Return the migration the database is stamped at, or None if unmanaged."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def upgrade_to_head(url: str) -> None:
    """Apply every pending migration up to the latest revision."""
    command.upgrade(_config(url), "head")


def stamp_head(url: str) -> None:
    """Mark the database as being at the latest revision without running DDL.

    For an existing database whose schema already matches the baseline (Neon,
    the local workshop), so Alembic adopts it instead of recreating its tables.
    """
    command.stamp(_config(url), "head")
