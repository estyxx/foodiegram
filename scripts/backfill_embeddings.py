"""Backfill recipe_embeddings for every recipe with a non-empty document.

Writes only to recipe_embeddings via save_embedding. Idempotent by default.
Run via:

    uv run python scripts/backfill_embeddings.py
    uv run python scripts/backfill_embeddings.py --limit 10
    uv run python scripts/backfill_embeddings.py --force
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from openai import OpenAI
from sqlalchemy import func
from sqlmodel import select

from foodiegram.ai.embeddings import EMBEDDING_MODEL, embed_texts, recipe_document
from foodiegram.settings import Settings
from foodiegram.storage._tables import RecipeEmbeddingRow
from foodiegram.storage.db import create_db_engine, get_session
from foodiegram.storage.recipes_db import RecipeRepository

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from foodiegram.domain.models import Recipe

_BATCH_SIZE = 100

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillReport:
    """Counts from one backfill_embeddings run."""

    considered: int
    skipped_empty: int
    already_embedded: int
    newly_embedded: int
    total_embeddings: int


def _embedded_codes(engine: Engine) -> set[str]:
    """Return every recipe_code that already has an embedding row."""
    with get_session(engine) as session:
        return set(session.exec(select(RecipeEmbeddingRow.recipe_code)).all())


def _embedding_count(engine: Engine) -> int:
    """Return the current row count in recipe_embeddings."""
    with get_session(engine) as session:
        return session.exec(
            select(func.count()).select_from(RecipeEmbeddingRow),
        ).one()


def _embed_in_batches(
    texts: list[str],
    *,
    client: OpenAI,
) -> list[list[float]]:
    """Call embed_texts in chunks of _BATCH_SIZE and return vectors in order."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        batch_vectors = embed_texts(batch, client=client, model=EMBEDDING_MODEL)
        if len(batch_vectors) != len(batch):
            msg = (
                f"OpenAI returned {len(batch_vectors)} vectors for "
                f"{len(batch)} inputs; aborting to avoid misaligned saves"
            )
            raise ValueError(msg)
        vectors.extend(batch_vectors)
    return vectors


def backfill_embeddings(
    *,
    repo: RecipeRepository,
    engine: Engine,
    client: OpenAI,
    force: bool,
    limit: int | None,
) -> BackfillReport:
    """Embed and store vectors for recipes that need them."""
    recipes = repo.find(is_recipe=True)
    considered = len(recipes)
    embedded_codes = _embedded_codes(engine)

    to_embed: list[tuple[Recipe, str]] = []
    skipped_empty = 0
    already_embedded = 0

    for recipe in recipes:
        document = recipe_document(recipe)
        if not document:
            skipped_empty += 1
            continue
        if recipe.code in embedded_codes and not force:
            already_embedded += 1
            continue
        to_embed.append((recipe, document))

    if limit is not None:
        to_embed = to_embed[:limit]

    newly_embedded = 0
    if to_embed:
        documents = [document for _recipe, document in to_embed]
        vectors = _embed_in_batches(documents, client=client)
        if len(vectors) != len(to_embed):
            msg = f"Expected {len(to_embed)} vectors after batching, got {len(vectors)}"
            raise ValueError(msg)
        for (recipe, _document), vector in zip(to_embed, vectors, strict=True):
            repo.save_embedding(recipe.code, vector, model=EMBEDDING_MODEL)
            newly_embedded += 1

    return BackfillReport(
        considered=considered,
        skipped_empty=skipped_empty,
        already_embedded=already_embedded,
        newly_embedded=newly_embedded,
        total_embeddings=_embedding_count(engine),
    )


def main() -> None:
    """Run the recipe embedding backfill."""
    parser = argparse.ArgumentParser(
        description="Backfill recipe_embeddings for recipes with a document.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed recipes that already have an embedding row.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Embed at most N recipes (after skips).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = Settings()
    engine = create_db_engine(settings.database_url)
    repo = RecipeRepository(engine)
    client = OpenAI(api_key=settings.require_openai_api_key())

    try:
        report = backfill_embeddings(
            repo=repo,
            engine=engine,
            client=client,
            force=args.force,
            limit=args.limit,
        )
    except ValueError:
        logger.exception("Backfill aborted")
        sys.exit(1)

    print(
        f"considered={report.considered}  skipped_empty={report.skipped_empty}  "
        f"already_embedded={report.already_embedded}  "
        f"newly_embedded={report.newly_embedded}  "
        f"total_embeddings={report.total_embeddings}",
    )


if __name__ == "__main__":
    main()
