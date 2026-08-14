"""Throwaway semantic-search quality check — embeds recipes inline and ranks queries.

Read-only on the database. Does not use recipe_embeddings or find_similar.
Run via: uv run python scripts/eval_search.py
"""

import logging
from typing import TYPE_CHECKING

from openai import OpenAI

from foodiegram.ai.embeddings import EMBEDDING_MODEL, embed_texts, recipe_document
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine
from foodiegram.storage.recipes_db import RecipeRepository

if TYPE_CHECKING:
    from foodiegram.domain.models import Recipe

QUERIES = [
    "dolce per colazione con proteine",
    "torta al cioccolato senza zucchero",
    "cena leggera di pesce",
    "quick vegetarian dinner",
    "qualcosa con la zucca",
]
TOP_K = 8
_BATCH_SIZE = 100

logger = logging.getLogger(__name__)


def _cosine(a: list[float], b: list[float]) -> float:
    """Return cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _embed_in_batches(
    texts: list[str],
    *,
    client: OpenAI,
) -> list[list[float]]:
    """Call embed_texts in chunks of _BATCH_SIZE and return vectors in order."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        vectors.extend(embed_texts(batch, client=client, model=EMBEDDING_MODEL))
    return vectors


def main() -> None:
    """Embed all recipes, score each query, and print ranked hits."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = Settings()
    engine = create_db_engine(settings.database_url)
    repo = RecipeRepository(engine)
    recipes = repo.find(is_recipe=True)

    client = OpenAI(api_key=settings.require_openai_api_key())

    embeddable: list[tuple[Recipe, str]] = [
        (recipe, document) for recipe in recipes if (document := recipe_document(recipe))
    ]
    skipped = len(recipes) - len(embeddable)
    if skipped:
        print(f"Skipped {skipped} recipes with empty documents")

    recipes_to_embed = [recipe for recipe, _document in embeddable]
    documents = [document for _recipe, document in embeddable]
    recipe_vectors = _embed_in_batches(documents, client=client)
    print(f"Embedded {len(recipe_vectors)} recipes")

    query_vectors = embed_texts(QUERIES, client=client, model=EMBEDDING_MODEL)

    for query, query_vector in zip(QUERIES, query_vectors, strict=True):
        print(f'\n=== Query: "{query}" ===')
        scored = [
            (recipe, _cosine(query_vector, vector))
            for recipe, vector in zip(recipes_to_embed, recipe_vectors, strict=True)
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        for recipe, score in scored[:TOP_K]:
            proteins = " ".join(recipe.proteins)
            title = recipe.title or ""
            dish = recipe.dish_type.value
            meal = recipe.meal_type.value
            print(
                f"{score:.3f}  {recipe.code:<12}  {dish}/{meal:<10}  "
                f"{proteins}  {title}",
            )


if __name__ == "__main__":
    main()
