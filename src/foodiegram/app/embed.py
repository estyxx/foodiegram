import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from foodiegram.ai.embeddings import EMBEDDING_MODEL, embed_texts, recipe_document
from foodiegram.domain.hashing import document_hash

if TYPE_CHECKING:
    from openai import OpenAI

    from foodiegram.domain.models import Recipe
    from foodiegram.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)

# OpenAI's embeddings endpoint accepts many inputs per call; batch to keep each
# request well under the token ceiling while minimising round-trips.
_BATCH_SIZE = 100


@dataclass(frozen=True)
class EmbedReport:
    """Roll-up of one embed run (or dry-run preview)."""

    considered: int
    needs_embedding: int
    embedded: int
    skipped_up_to_date: int
    skipped_empty: int


def _embed_in_batches(documents: list[str], *, client: OpenAI) -> list[list[float]]:
    """Embed documents in fixed-size batches, preserving input order."""
    vectors: list[list[float]] = []
    for start in range(0, len(documents), _BATCH_SIZE):
        chunk = documents[start : start + _BATCH_SIZE]
        vectors.extend(embed_texts(chunk, client=client))
    return vectors


def _select(
    recipes: list[Recipe],
    *,
    stored_hashes: dict[str, str | None],
    force: bool,
    codes: set[str] | None,
) -> tuple[list[tuple[Recipe, str]], int, int]:
    """Return (recipe, document) pairs to embed plus up-to-date and empty counts.

    Without force, a recipe is skipped when it already has an embedding whose
    stored source hash equals the current document hash (G6 staleness check);
    recipes with no embedding row, or a differing hash, are (re)embedded.
    """
    to_embed: list[tuple[Recipe, str]] = []
    skipped_up_to_date = 0
    skipped_empty = 0
    for recipe in recipes:
        if codes is not None and recipe.code not in codes:
            continue
        document = recipe_document(recipe)
        if not document:
            skipped_empty += 1
            continue
        current = document_hash(document)
        fresh = recipe.code in stored_hashes and stored_hashes[recipe.code] == current
        if not force and fresh:
            skipped_up_to_date += 1
            continue
        to_embed.append((recipe, document))
    return to_embed, skipped_up_to_date, skipped_empty


def embed_recipes(
    *,
    recipes: RecipeRepository,
    client: OpenAI,
    force: bool = False,
    codes: set[str] | None = None,
    dry_run: bool = False,
) -> EmbedReport:
    """Embed stale or missing recipe documents and store the refreshed hash.

    Default (force=False) re-embeds only recipes whose document hash differs
    from the stored embedding_source_hash, plus recipes with no embedding row.
    force re-embeds every non-empty document; codes restricts to the given set.
    """
    candidates = recipes.find(is_recipe=True)
    stored_hashes = recipes.embedding_source_hashes()
    to_embed, skipped_up_to_date, skipped_empty = _select(
        candidates,
        stored_hashes=stored_hashes,
        force=force,
        codes=codes,
    )

    embedded = 0
    if to_embed and not dry_run:
        vectors = _embed_in_batches([doc for _, doc in to_embed], client=client)
        for (recipe, document), vector in zip(to_embed, vectors, strict=True):
            recipes.save_embedding(
                recipe.code,
                vector,
                model=EMBEDDING_MODEL,
                source_hash=document_hash(document),
            )
            embedded += 1

    logger.info(
        "Embed: considered=%d needs=%d embedded=%d up_to_date=%d empty=%d",
        len(candidates),
        len(to_embed),
        embedded,
        skipped_up_to_date,
        skipped_empty,
    )
    return EmbedReport(
        considered=len(candidates),
        needs_embedding=len(to_embed),
        embedded=embedded,
        skipped_up_to_date=skipped_up_to_date,
        skipped_empty=skipped_empty,
    )
