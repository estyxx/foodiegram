import logging
from pathlib import Path
from typing import Annotated

import typer

from foodiegram.settings import Settings
from foodiegram.storage import maintenance
from foodiegram.storage.db import database_label

app = typer.Typer(help="Foodiegram / Dispensa command-line tools.")
db_app = typer.Typer(help="Database maintenance for the working Postgres database.")
app.add_typer(db_app, name="db")

logger = logging.getLogger(__name__)


def _settings() -> Settings:
    """Load application settings from the environment."""
    return Settings()


@db_app.command("ping")
def db_ping() -> None:
    """Connect to the working database and report success."""
    settings = _settings()
    try:
        maintenance.ping_database(database_url=settings.database_url)
    except Exception:
        label = database_label(settings.database_url)
        logger.exception("Database ping failed (%s)", label)
        raise typer.Exit(code=1) from None
    typer.echo(f"OK {database_label(settings.database_url)}")


@db_app.command("create-database")
def db_create_database(
    *,
    test: Annotated[
        bool,
        typer.Option("--test", help="Create DATABASE_URL_TEST instead of DATABASE_URL."),
    ] = False,
) -> None:
    """Create the Postgres database from DATABASE_URL when it does not exist."""
    settings = _settings()
    database_url = settings.database_url_test if test else settings.database_url
    created = maintenance.ensure_database(database_url=database_url)
    label = database_label(database_url)
    if created:
        typer.echo(f"Created {label}")
    else:
        typer.echo(f"Already exists: {label}")


@db_app.command("create-tables")
def db_create_tables() -> None:
    """Create any missing tables on the working database."""
    settings = _settings()
    maintenance.create_tables(database_url=settings.database_url)
    typer.echo(f"Tables ready on {database_label(settings.database_url)}")


@db_app.command("dump")
def db_dump(
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Destination .dump file path."),
    ] = None,
) -> None:
    """Back up the working database with pg_dump (custom format)."""
    settings = _settings()
    destination = output or maintenance.default_dump_path()
    maintenance.dump_database(database_url=settings.database_url, output=destination)
    typer.echo(f"Wrote {destination}")


@db_app.command("restore")
def db_restore(
    dump_path: Annotated[Path, typer.Argument(help="Custom-format pg_dump file.")],
    *,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm destructive restore."),
    ] = False,
) -> None:
    """Restore a pg_dump backup into the working database."""
    settings = _settings()
    maintenance.refuse_destructive_on_prod(
        database_url=settings.database_url,
        action="restore",
    )
    maintenance.require_confirmation(
        confirmed=yes,
        action="restore",
        database_url=settings.database_url,
    )
    typer.echo(
        f"Restoring {dump_path} into {database_label(settings.database_url)}",
    )
    maintenance.restore_database(database_url=settings.database_url, dump_path=dump_path)
    typer.echo("Restore complete.")


@db_app.command("reset")
def db_reset(
    *,
    yes: Annotated[bool, typer.Option("--yes", help="Confirm drop + recreate.")] = False,
) -> None:
    """Drop and recreate every table on the working database."""
    settings = _settings()
    maintenance.refuse_destructive_on_prod(
        database_url=settings.database_url,
        action="reset",
    )
    maintenance.require_confirmation(
        confirmed=yes,
        action="reset",
        database_url=settings.database_url,
    )
    typer.echo(f"Resetting {database_label(settings.database_url)}")
    maintenance.reset_database(database_url=settings.database_url)
    typer.echo("Reset complete.")


def main() -> None:
    """Run the Foodiegram CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    app()


if __name__ == "__main__":
    main()
