"""Backfill caption_hash and embedding_source_hash for existing rows.

Additive and idempotent: only fills rows whose hash is currently null, so a
second run sets nothing. Honours DATABASE_URL (default local Postgres) and
refuses a production host unless --yes. Run via:

    uv run python scripts/backfill_hashes.py --dry-run
    uv run python scripts/backfill_hashes.py
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlmodel import col, select

from foodiegram.ai.embeddings import recipe_document
from foodiegram.domain.hashing import caption_hash, document_hash
from foodiegram.settings import Settings
from foodiegram.storage._tables import RecipeEmbeddingRow, RecipeRow
from foodiegram.storage.db import (
    create_db_engine,
    database_label,
    get_session,
    init_db,
    looks_like_prod,
)
from foodiegram.storage.recipes_db import RecipeRepository

if TYPE_CHECKING:
    from sqlalchemy import Engine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillReport:
    """Counts from one backfill_hashes run."""

    caption_hashes_set: int
    embedding_hashes_set: int
    skipped_present: int


def _count_already_present(engine: Engine) -> int:
    """Count rows that already carry the relevant hash (nothing to do)."""
    with get_session(engine) as session:
        captioned_hashed = session.exec(
            select(func.count())
            .select_from(RecipeRow)
            .where(
                col(RecipeRow.caption).is_not(None),
                col(RecipeRow.caption_hash).is_not(None),
            ),
        ).one()
        embeddings_hashed = session.exec(
            select(func.count())
            .select_from(RecipeEmbeddingRow)
            .where(col(RecipeEmbeddingRow.embedding_source_hash).is_not(None)),
        ).one()
    return captioned_hashed + embeddings_hashed


def _backfill_caption_hashes(engine: Engine, *, dry_run: bool) -> int:
    """Set caption_hash on captioned recipes that lack it. Return the count set."""
    set_count = 0
    with get_session(engine) as session:
        rows = session.exec(
            select(RecipeRow).where(
                col(RecipeRow.caption).is_not(None),
                col(RecipeRow.caption_hash).is_(None),
            ),
        ).all()
        for row in rows:
            digest = caption_hash(row.caption)
            if digest is None:
                continue
            if not dry_run:
                row.caption_hash = digest
                session.add(row)
            set_count += 1
        if not dry_run:
            session.commit()
    return set_count


def _backfill_embedding_hashes(
    engine: Engine,
    *,
    repo: RecipeRepository,
    dry_run: bool,
) -> int:
    """Set embedding_source_hash from the current document. Return the count set."""
    set_count = 0
    with get_session(engine) as session:
        rows = session.exec(
            select(RecipeEmbeddingRow).where(
                col(RecipeEmbeddingRow.embedding_source_hash).is_(None),
            ),
        ).all()
        for row in rows:
            recipe = repo.get(row.recipe_code)
            if recipe is None:
                continue
            digest = document_hash(recipe_document(recipe))
            if not dry_run:
                row.embedding_source_hash = digest
                session.add(row)
            set_count += 1
        if not dry_run:
            session.commit()
    return set_count


def main() -> None:
    """Backfill both hash columns for existing rows."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Backfill caption_hash and embedding_source_hash columns.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing anything.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Allow running against a production database host.",
    )
    args = parser.parse_args()

    settings = Settings()
    label = database_label(settings.database_url)
    logger.info("Target database: %s", label)

    if looks_like_prod(settings.database_url) and not args.yes:
        print(f"Refusing to run against prod ({label}); pass --yes.", file=sys.stderr)
        sys.exit(1)

    engine = create_db_engine(settings.database_url)
    init_db(engine)
    repo = RecipeRepository(engine)

    skipped_present = _count_already_present(engine)
    caption_hashes_set = _backfill_caption_hashes(engine, dry_run=args.dry_run)
    embedding_hashes_set = _backfill_embedding_hashes(
        engine,
        repo=repo,
        dry_run=args.dry_run,
    )

    report = BackfillReport(
        caption_hashes_set=caption_hashes_set,
        embedding_hashes_set=embedding_hashes_set,
        skipped_present=skipped_present,
    )
    mode = "DRY-RUN" if args.dry_run else "APPLIED"
    print(
        f"[{mode}] caption_hashes_set={report.caption_hashes_set}  "
        f"embedding_hashes_set={report.embedding_hashes_set}  "
        f"skipped_present={report.skipped_present}",
    )


if __name__ == "__main__":
    main()
