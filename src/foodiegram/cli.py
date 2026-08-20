import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from openai import OpenAI

from foodiegram.ai.batch import PROMPT_VERSION, log_batch_status
from foodiegram.app import (
    backfill_images,
    embed,
    extraction,
    ingest,
    promotion,
    sync_all,
)
from foodiegram.domain.errors import FoodiegramError
from foodiegram.images import configure, upload_thumbnail
from foodiegram.settings import Settings
from foodiegram.storage import maintenance
from foodiegram.storage.db import (
    create_db_engine,
    database_label,
    init_db,
    looks_like_prod,
)
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.recipes_db import RecipeRepository

app = typer.Typer(help="Foodiegram / Dispensa command-line tools.")
db_app = typer.Typer(help="Database maintenance for the working Postgres database.")
sync_app = typer.Typer(help="Offline Stage B ingestion pipeline (food.json → recipes).")
app.add_typer(db_app, name="db")
app.add_typer(sync_app, name="sync")

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


def _guard_writable(settings: Settings, *, dry_run: bool, yes: bool) -> None:
    """Print the target database and refuse a prod host unless --yes (or dry-run)."""
    label = database_label(settings.database_url)
    typer.echo(f"Target database: {label}")
    if not dry_run and looks_like_prod(settings.database_url) and not yes:
        typer.echo(f"Refusing to write to prod ({label}); pass --yes.", err=True)
        raise typer.Exit(code=1)


def _ingest_flags(result: ingest.IngestItemResult) -> str:
    """Render one ingest item's flags for the per-item report line."""
    if result.unchanged:
        return "unchanged"
    parts: list[str] = []
    if result.is_new:
        parts.append("new")
    if result.caption_changed:
        parts.append("caption")
    if result.image_fixed:
        parts.append("image")
    return "+".join(parts)


@sync_app.command("dedupe-links")
def sync_dedupe_links(
    links_file: Annotated[
        Path,
        typer.Argument(help="IGbulkCollector links .txt (one URL per line)."),
    ],
    *,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Cleaned output (default: <input>.deduped.txt)."),
    ] = None,
) -> None:
    """Drop duplicate and already-stored shortcodes from a links file."""
    settings = _settings()
    typer.echo(f"Target database: {database_label(settings.database_url)}")
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    repo = RecipeRepository(engine)
    known = {recipe.code for recipe in repo.list_all()}
    report = ingest.dedupe_links(links_file=links_file, known_codes=known)
    destination = output or links_file.with_suffix(".deduped.txt")
    body = "\n".join(report.written_urls)
    destination.write_text(body + "\n" if body else "", encoding="utf-8")
    typer.echo(
        f"read={report.read}  unique={report.unique}  "
        f"already_in_db={report.already_in_db}  written={report.written}",
    )
    typer.echo(f"Wrote {destination}")


@sync_app.command("ingest")
def sync_ingest(
    food_json: Annotated[Path, typer.Argument(help="IGbulkDL food.json log.")],
    *,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Report actions without writing or uploading."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Allow writing to a production-looking database."),
    ] = False,
) -> None:
    """Reconcile a food.json against the DB: stubs, captions, durable images."""
    settings = _settings()
    _guard_writable(settings, dry_run=dry_run, yes=yes)
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    repo = RecipeRepository(engine)
    if not dry_run:
        configure(config=settings.require_cloudinary())
    items = ingest.parse_food_items(path=food_json)
    report = ingest.ingest_food_json(
        recipes=repo,
        items=items,
        upload=upload_thumbnail,
        dry_run=dry_run,
    )
    for result in report.results:
        typer.echo(f"{result.code}  {_ingest_flags(result)}")
    typer.echo(
        f"new={report.new}  caption_changed={report.caption_changed}  "
        f"image_fixed={report.image_fixed}  unchanged={report.unchanged}",
    )
    codes = report.codes_needing_extraction
    typer.echo(f"needs extraction ({len(codes)}): {' '.join(codes) if codes else '-'}")


@sync_app.command("backfill-images")
def sync_backfill_images(
    *,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Report what would be uploaded without writing."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Allow writing to a production-looking database."),
    ] = False,
) -> None:
    """Re-upload a durable image for every stored recipe missing or with a broken one.

    Scans the whole DB, not one food.json batch — catches recipes that fell out
    of the current food.json export before ever getting a Cloudinary upload.
    """
    settings = _settings()
    _guard_writable(settings, dry_run=dry_run, yes=yes)
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    if not dry_run:
        configure(config=settings.require_cloudinary())
    report = backfill_images.backfill_images(
        recipes=RecipeRepository(engine),
        upload=upload_thumbnail,
        dry_run=dry_run,
    )
    for code in report.fixed_codes:
        typer.echo(code)
    for code in report.failed_codes:
        typer.echo(f"{code}  FAILED")
    typer.echo(f"fixed={report.fixed}  failed={report.failed}")


@sync_app.command("extract")
def sync_extract(
    *,
    all_: Annotated[
        bool,
        typer.Option("--all", help="Re-submit every eligible recipe, not just missing."),
    ] = False,
    codes: Annotated[
        list[str] | None,
        typer.Option("--codes", help="Restrict submission to these recipe codes."),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", help="Submit at most this many recipes."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Select and report without creating a batch."),
    ] = False,
) -> None:
    """Submit an OpenAI extraction batch for recipes needing extraction."""
    settings = _settings()
    typer.echo(f"Target database: {database_label(settings.database_url)}")
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    count = extraction.submit_batch(
        settings,
        recipes=RecipeRepository(engine),
        extractions=ExtractionRepository(engine),
        only_missing=not all_,
        limit=limit,
        only_codes=set(codes) if codes else None,
        dry_run=dry_run,
    )
    action = "Would submit" if dry_run else "Submitted"
    typer.echo(f"{action} {count} recipe(s) at prompt version {PROMPT_VERSION}.")


@sync_app.command("status")
def sync_status(
    batch_id: Annotated[
        str | None,
        typer.Option("--batch", help="Batch id (default: last submitted)."),
    ] = None,
) -> None:
    """Report the status and request counts of a submitted OpenAI batch job."""
    settings = _settings()
    log_batch_status(settings, batch_id)


@sync_app.command("apply")
def sync_apply(
    batch_id: Annotated[
        str | None,
        typer.Option("--batch", help="Batch id (default: last submitted)."),
    ] = None,
    *,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Allow writing to a production-looking database."),
    ] = False,
) -> None:
    """Download a completed OpenAI batch and append its results as extractions.

    Writes extraction history only — never touches recipes. Run `sync promote`
    afterwards to merge these extractions into recipes.
    """
    settings = _settings()
    _guard_writable(settings, dry_run=False, yes=yes)
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    extraction.apply_batch(
        settings,
        batch_id,
        extractions=ExtractionRepository(engine),
        applied_at=datetime.now(tz=UTC),
    )


@sync_app.command("promote")
def sync_promote(
    *,
    version: Annotated[
        str,
        typer.Option("--version", help="Prompt version to promote."),
    ] = PROMPT_VERSION,
    batch: Annotated[
        str | None,
        typer.Option("--batch", help="Restrict to a single batch id."),
    ] = None,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Persist promotions (default is a dry run)."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Allow writing to a production-looking database."),
    ] = False,
) -> None:
    """Promote the latest extraction at a prompt version into each recipe."""
    settings = _settings()
    dry_run = not apply
    _guard_writable(settings, dry_run=dry_run, yes=yes)
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    report = promotion.promote_version(
        recipes=RecipeRepository(engine),
        extractions=ExtractionRepository(engine),
        version=version,
        batch_id=batch,
        dry_run=dry_run,
    )
    mode = "dry-run" if report.dry_run else "applied"
    typer.echo(
        f"promote v{report.version} ({mode}): considered={report.considered} "
        f"changed={report.changed} promoted={report.promoted} "
        f"missing={report.missing_recipe} "
        f"preserved_fields={report.total_skipped_fields}",
    )


@sync_app.command("embed")
def sync_embed(
    *,
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-embed every recipe, not just stale/missing."),
    ] = False,
    codes: Annotated[
        list[str] | None,
        typer.Option("--codes", help="Restrict embedding to these recipe codes."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Report what would be embedded without writing."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Allow writing to a production-looking database."),
    ] = False,
) -> None:
    """Re-embed changed recipes (default) plus any missing embeddings."""
    settings = _settings()
    _guard_writable(settings, dry_run=dry_run, yes=yes)
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    client = OpenAI(api_key=settings.require_openai_api_key())
    report = embed.embed_recipes(
        recipes=RecipeRepository(engine),
        client=client,
        force=force,
        codes=set(codes) if codes else None,
        dry_run=dry_run,
    )
    scope = "force" if force else "changed"
    typer.echo(
        f"embed ({scope}): considered={report.considered} "
        f"needs={report.needs_embedding} embedded={report.embedded} "
        f"up_to_date={report.skipped_up_to_date} empty={report.skipped_empty}",
    )


@sync_app.command("all")
def sync_all_cmd(
    food_json: Annotated[Path, typer.Argument(help="IGbulkDL food.json log.")],
    *,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Propagate a dry run to every stage."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Allow writing to a production-looking database."),
    ] = False,
) -> None:
    """Run Stage B in order: ingest -> extract -> promote -> embed --changed."""
    settings = _settings()
    _guard_writable(settings, dry_run=dry_run, yes=yes)
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    repo = RecipeRepository(engine)
    extractions = ExtractionRepository(engine)
    if not dry_run:
        configure(config=settings.require_cloudinary())
    client = OpenAI(api_key=settings.require_openai_api_key())

    def _ingest() -> str:
        items = ingest.parse_food_items(path=food_json)
        report = ingest.ingest_food_json(
            recipes=repo,
            items=items,
            upload=upload_thumbnail,
            dry_run=dry_run,
        )
        return (
            f"new={report.new} caption_changed={report.caption_changed} "
            f"image_fixed={report.image_fixed} unchanged={report.unchanged}"
        )

    def _extract() -> str:
        count = extraction.submit_batch(
            settings,
            recipes=repo,
            extractions=extractions,
            only_missing=True,
            dry_run=dry_run,
        )
        return f"submitted={count} (async batch; apply after completion)"

    def _promote() -> str:
        report = promotion.promote_version(
            recipes=repo,
            extractions=extractions,
            version=PROMPT_VERSION,
            dry_run=dry_run,
        )
        return f"promoted={report.promoted} changed={report.changed}"

    def _embed() -> str:
        report = embed.embed_recipes(recipes=repo, client=client, dry_run=dry_run)
        return f"embedded={report.embedded} needs={report.needs_embedding}"

    stages = (
        sync_all.Stage(name="ingest", run=_ingest),
        sync_all.Stage(name="extract", run=_extract),
        sync_all.Stage(name="promote", run=_promote),
        sync_all.Stage(name="embed", run=_embed),
    )
    try:
        summaries = sync_all.run_stages(stages)
    except FoodiegramError as exc:
        logger.exception("sync all stopped on a stage error")
        typer.echo(f"sync all failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for line in summaries:
        typer.echo(line)
    typer.echo(
        "NOTE: extract submits an async batch; promote/embed acted on "
        "already-applied extractions. Re-run 'sync promote' and 'sync embed' "
        "after the batch completes.",
    )


def main() -> None:
    """Run the Foodiegram CLI."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    app()


if __name__ == "__main__":
    main()
