import math

from sqlalchemy import Engine, func, select

from foodiegram.ai.embeddings import recipe_document
from foodiegram.domain.enums import MealType
from foodiegram.domain.hashing import document_hash
from foodiegram.domain.models import Recipe
from foodiegram.domain.similarity import cosine_similarity
from foodiegram.storage._tables import RecipeEmbeddingRow
from foodiegram.storage.db import get_session
from foodiegram.storage.recipes_db import RecipeRepository

_MODEL = "text-embedding-3-small"
_LIMIT_TWO = 2


def _recipe(
    code: str,
    *,
    meal_type: MealType = MealType.LUNCH,
) -> Recipe:
    """Build a minimal recipe for embedding tests."""
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


def test_save_embedding_round_trips_through_get_embedding(engine: Engine) -> None:
    """save_embedding stores a vector that get_embedding reads back."""
    repo = RecipeRepository(engine)
    repo.save(_recipe("A1"))
    vector = [1.0, 0.0, 0.0]

    repo.save_embedding("A1", vector, model=_MODEL)

    assert repo.get_embedding("A1") == vector


def test_save_embedding_upserts_one_row_per_recipe(engine: Engine) -> None:
    """A second save for the same code replaces the stored vector."""
    repo = RecipeRepository(engine)
    repo.save(_recipe("A1"))
    first = [1.0, 0.0, 0.0]
    second = [0.0, 1.0, 0.0]

    repo.save_embedding("A1", first, model=_MODEL)
    repo.save_embedding("A1", second, model=_MODEL)

    assert repo.get_embedding("A1") == second

    with engine.connect() as connection:
        count = connection.execute(
            select(func.count()).select_from(RecipeEmbeddingRow),
        ).scalar_one()
    assert count == 1


def test_save_embedding_stores_source_hash(engine: Engine) -> None:
    """The embedding write path persists the document hash alongside the vector."""
    repo = RecipeRepository(engine)
    recipe = _recipe("A1")
    repo.save(recipe)
    expected = document_hash(recipe_document(recipe))

    repo.save_embedding("A1", [1.0, 0.0, 0.0], model=_MODEL, source_hash=expected)

    with get_session(engine) as session:
        row = session.get(RecipeEmbeddingRow, "A1")
    assert row is not None
    assert row.embedding_source_hash == expected


def test_find_similar_orders_by_closeness_with_descending_scores(engine: Engine) -> None:
    """find_similar ranks embedded recipes by cosine similarity to the query."""
    repo = RecipeRepository(engine)
    repo.save(_recipe("CLOSE"))
    repo.save(_recipe("NEAR"))
    repo.save(_recipe("FAR"))
    query = [1.0, 0.0, 0.0]
    repo.save_embedding("CLOSE", [1.0, 0.0, 0.0], model=_MODEL)
    repo.save_embedding("NEAR", [0.8, 0.2, 0.0], model=_MODEL)
    repo.save_embedding("FAR", [0.0, 1.0, 0.0], model=_MODEL)

    results = repo.find_similar(query, limit=3)

    assert [recipe.code for recipe, _score in results] == ["CLOSE", "NEAR", "FAR"]
    scores = [score for _recipe, score in results]
    assert scores == sorted(scores, reverse=True)
    assert math.isclose(scores[0], 1.0)


def test_find_similar_honours_limit(engine: Engine) -> None:
    """find_similar returns at most limit tuples."""
    repo = RecipeRepository(engine)
    for code in ("A", "B", "C"):
        repo.save(_recipe(code))
        repo.save_embedding(code, [1.0, 0.0, 0.0], model=_MODEL)

    results = repo.find_similar([1.0, 0.0, 0.0], limit=_LIMIT_TWO)

    assert len(results) == _LIMIT_TWO


def test_find_similar_applies_meal_type_filter(engine: Engine) -> None:
    """Structured filters delegate to find() before ranking."""
    repo = RecipeRepository(engine)
    repo.save(_recipe("BRK1", meal_type=MealType.BREAKFAST))
    repo.save(_recipe("BRK2", meal_type=MealType.BREAKFAST))
    repo.save(_recipe("DIN1", meal_type=MealType.DINNER))
    repo.save_embedding("BRK1", [1.0, 0.0, 0.0], model=_MODEL)
    repo.save_embedding("BRK2", [0.9, 0.1, 0.0], model=_MODEL)
    repo.save_embedding("DIN1", [1.0, 0.0, 0.0], model=_MODEL)

    results = repo.find_similar(
        [1.0, 0.0, 0.0],
        meal_type=MealType.BREAKFAST,
        limit=8,
    )

    assert [recipe.code for recipe, _score in results] == ["BRK1", "BRK2"]
    assert all(recipe.meal_type is MealType.BREAKFAST for recipe, _score in results)


def test_find_similar_excludes_recipes_without_embeddings(engine: Engine) -> None:
    """A filtered match with no embedding row is skipped without error."""
    repo = RecipeRepository(engine)
    repo.save(_recipe("HAS"))
    repo.save(_recipe("MISSING"))
    repo.save_embedding("HAS", [1.0, 0.0, 0.0], model=_MODEL)

    results = repo.find_similar([1.0, 0.0, 0.0], limit=8)

    assert [recipe.code for recipe, _score in results] == ["HAS"]


def test_cosine_similarity_handles_identical_orthogonal_and_zero_vectors() -> None:
    """Identical vectors score 1.0; orthogonal and zero vectors score 0.0."""
    assert math.isclose(cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]), 1.0)
    assert math.isclose(cosine_similarity([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]), 0.0)
    assert math.isclose(cosine_similarity([0.0, 0.0, 0.0], [1.0, 0.0, 0.0]), 0.0)
