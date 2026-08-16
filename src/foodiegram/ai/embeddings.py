from typing import TYPE_CHECKING

from foodiegram.domain.enums import CuisineType, DishType, MealType

if TYPE_CHECKING:
    from collections.abc import Sequence

    from openai import OpenAI

    from foodiegram.domain.models import Recipe

EMBEDDING_MODEL = "text-embedding-3-small"


def recipe_document(recipe: Recipe) -> str:
    """Build meaning-carrying text to embed for one recipe.

    Not just the title — semantic search should match on what the dish IS.
    Empty parts are skipped; returns a single newline-joined string.
    """
    parts: list[str] = []

    if recipe.title:
        parts.append(recipe.title)

    if recipe.summary:
        parts.append(recipe.summary)

    classification = _classification_line(recipe)
    if classification:
        parts.append(classification)

    if recipe.proteins:
        parts.append(" ".join(recipe.proteins))

    if recipe.ingredients:
        parts.append(" ".join(recipe.ingredients))

    return "\n".join(parts)


def _classification_line(recipe: Recipe) -> str:
    """Return dish, meal, and cuisine on one line, skipping unknown values."""
    tokens: list[str] = []
    if recipe.dish_type is not DishType.UNKNOWN:
        tokens.append(recipe.dish_type.value)
    if recipe.meal_type is not MealType.UNKNOWN:
        tokens.append(recipe.meal_type.value)
    if recipe.cuisine_type is not CuisineType.UNKNOWN:
        tokens.append(recipe.cuisine_type.value)
    return " ".join(tokens)


def embed_texts(
    texts: Sequence[str],
    *,
    client: OpenAI,
    model: str = EMBEDDING_MODEL,
) -> list[list[float]]:
    """One 1536-float vector per input text, in the same order."""
    if not texts:
        return []

    response = client.embeddings.create(input=list(texts), model=model)
    ordered = sorted(response.data, key=lambda item: item.index)
    return [item.embedding for item in ordered]
