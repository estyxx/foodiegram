from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine

from foodiegram.app.search_recipes import search_recipes_semantic
from foodiegram.domain.enums import MealType
from foodiegram.domain.models import Recipe
from foodiegram.storage.recipes_db import RecipeRepository

_MODEL = "text-embedding-3-small"
_QUERY_VECTOR = [1.0, 0.0, 0.0]


def _recipe(
    code: str,
    *,
    meal_type: MealType = MealType.LUNCH,
) -> Recipe:
    """Build a minimal recipe for semantic search tests."""
    return Recipe(
        code=code,
        pk="1",
        post_url=None,
        caption=None,
        title=f"Recipe {code}",
        ingredients=["water"],
        instructions=["boil"],
        meal_type=meal_type,
    )


def test_search_recipes_semantic_empty_query_skips_embedding(
    engine: Engine,
) -> None:
    """Whitespace-only queries return [] without calling OpenAI."""
    repo = RecipeRepository(engine)
    client = MagicMock()

    assert search_recipes_semantic(recipes=repo, client=client, query="   ") == []

    client.embeddings.create.assert_not_called()


def test_search_recipes_semantic_embeds_query_and_returns_scores(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The use-case embeds the query and returns find_similar tuples unchanged."""
    repo = RecipeRepository(engine)
    repo.save(_recipe("CLOSE"))
    repo.save(_recipe("FAR"))
    repo.save_embedding("CLOSE", [1.0, 0.0, 0.0], model=_MODEL)
    repo.save_embedding("FAR", [0.0, 1.0, 0.0], model=_MODEL)

    captured: list[str] = []

    def fake_embed_texts(
        texts: list[str],
        *,
        client: MagicMock,
        model: str,
    ) -> list[list[float]]:
        _ = client
        captured.extend(texts)
        assert model == _MODEL
        return [_QUERY_VECTOR]

    monkeypatch.setattr(
        "foodiegram.app.search_recipes.embed_texts",
        fake_embed_texts,
    )
    client = MagicMock()

    results = search_recipes_semantic(
        recipes=repo,
        client=client,
        query="dolce per colazione con proteine",
        limit=2,
    )

    assert captured == ["dolce per colazione con proteine"]
    assert [recipe.code for recipe, _score in results] == ["CLOSE", "FAR"]
    scores = [score for _recipe, score in results]
    assert scores == sorted(scores, reverse=True)


def test_search_recipes_semantic_passes_facet_filters(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Facet filters are forwarded to find_similar before ranking."""
    repo = RecipeRepository(engine)
    repo.save(_recipe("BRK", meal_type=MealType.BREAKFAST))
    repo.save(_recipe("DIN", meal_type=MealType.DINNER))
    repo.save_embedding("BRK", [1.0, 0.0, 0.0], model=_MODEL)
    repo.save_embedding("DIN", [1.0, 0.0, 0.0], model=_MODEL)

    def fake_embed(
        _texts: list[str],
        *,
        client: MagicMock,
        model: str,
    ) -> list[list[float]]:
        _ = client
        _ = model
        return [_QUERY_VECTOR]

    monkeypatch.setattr(
        "foodiegram.app.search_recipes.embed_texts",
        fake_embed,
    )
    client = MagicMock()

    results = search_recipes_semantic(
        recipes=repo,
        client=client,
        query="breakfast",
        meal_type=MealType.BREAKFAST,
        limit=8,
    )

    assert [recipe.code for recipe, _score in results] == ["BRK"]
