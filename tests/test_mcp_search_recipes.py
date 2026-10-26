from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import Engine

from dispensa.ai.embeddings import EMBEDDING_MODEL
from dispensa.deps import Deps
from dispensa.domain.enums import Difficulty, MedCategory
from dispensa.domain.models import CategoryServing, Recipe
from dispensa.domain.pantry import PantryItem
from dispensa.mcp_server.server import search_recipes
from dispensa.storage.exercise_log_db import ExerciseLogRepository
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository

_QUERY_VECTOR = [1.0, 0.0, 0.0]
# Closest first: a query for [1, 0, 0] ranks these in this order.
_BEST = [1.0, 0.0, 0.0]
_GOOD = [0.8, 0.6, 0.0]
_FAIR = [0.6, 0.8, 0.0]
_HALF_SERVING = 0.5
_MISSING_LINES = 2


@pytest.fixture
def deps(db_engine: Engine) -> Generator[Deps]:
    """Wire repositories, fake the query embedding, and point the tool at both."""
    wired = Deps(
        recipes=RecipeRepository(db_engine),
        extractions=ExtractionRepository(db_engine),
        user_state=UserStateRepository(db_engine),
        plans=PlanRepository(db_engine),
        pantry=PantryRepository(db_engine),
        targets=TargetRepository(db_engine),
        exercise_log=ExerciseLogRepository(db_engine),
    )
    with (
        patch("dispensa.mcp_server.server.get_deps", return_value=wired),
        patch("dispensa.mcp_server.server.get_openai_client", return_value=MagicMock()),
        patch(
            "dispensa.app.search_recipes.embed_texts",
            return_value=[_QUERY_VECTOR],
        ),
    ):
        yield wired


def _save(
    deps: Deps,
    code: str,
    *,
    vector: list[float],
    category: MedCategory,
    ingredients: tuple[str, ...] = ("acqua",),
) -> None:
    """Store an embedded one-category recipe."""
    deps.recipes.save(
        Recipe(
            code=code,
            pk=None,
            post_url=None,
            caption=None,
            title=f"Recipe {code}",
            ingredients=list(ingredients),
            instructions=["do it"],
            difficulty=Difficulty.EASY,
            mediterranean_categories=[
                CategoryServing(category=category, servings=_HALF_SERVING),
            ],
        ),
    )
    deps.recipes.save_embedding(code, vector, model=EMBEDDING_MODEL)


def test_hits_carry_balance_fields_and_pantry_counts(deps: Deps) -> None:
    """Each hit has difficulty, categories with servings, and have/missing counts."""
    _save(
        deps,
        "LEG1",
        vector=_BEST,
        category=MedCategory.LEGUMES,
        ingredients=("200 g ceci", "160 g pasta", "sale"),
    )
    deps.pantry.add(PantryItem(name="chickpeas", kind="staple"))
    deps.user_state.set_favorite("LEG1", is_favorite=True)

    (hit,) = search_recipes(query="pasta e ceci")

    assert hit["code"] == "LEG1"
    assert hit["difficulty"] == "easy"
    assert hit["mediterranean_categories"] == [
        {"category": "legumes", "servings": _HALF_SERVING, "is_oily_fish": False},
    ]
    assert hit["pantry_have"] == 1
    assert hit["pantry_missing"] == _MISSING_LINES
    assert hit["is_favorite"] is True
    assert hit["score"] == pytest.approx(1.0)


def test_category_keeps_only_recipes_that_count_toward_it(deps: Deps) -> None:
    """Category filters on what the balance counts, before ranking."""
    _save(deps, "FISH1", vector=_BEST, category=MedCategory.FISH)
    _save(deps, "LEG1", vector=_GOOD, category=MedCategory.LEGUMES)

    hits = search_recipes(query="cena", category="legumes")

    assert [hit["code"] for hit in hits] == ["LEG1"]


@pytest.mark.usefixtures("deps")
def test_unknown_category_lists_the_valid_ones() -> None:
    """A bad category is a ValueError the model can correct from the message."""
    with pytest.raises(ValueError, match=r"one of fish, legumes, .*got 'beans'"):
        search_recipes(query="cena", category="beans")


def test_pantry_only_filters_before_the_limit(deps: Deps) -> None:
    """The best pantry hit is returned even when better non-pantry hits outrank it."""
    _save(deps, "TOP", vector=_BEST, category=MedCategory.FISH)
    _save(deps, "MID", vector=_GOOD, category=MedCategory.FISH)
    _save(
        deps,
        "USES",
        vector=_FAIR,
        category=MedCategory.EGGS,
        ingredients=("2 uova", "sale"),
    )
    deps.pantry.add(PantryItem(name="uova", kind="fresh"))

    hits = search_recipes(query="cena", pantry_only=True, limit=1)

    assert [hit["code"] for hit in hits] == ["USES"]


def test_pantry_only_with_an_empty_pantry_returns_nothing(deps: Deps) -> None:
    """Nothing uses an empty pantry, so nothing is returned."""
    _save(deps, "TOP", vector=_BEST, category=MedCategory.FISH)

    assert search_recipes(query="cena", pantry_only=True) == []


def test_empty_query_returns_nothing(deps: Deps) -> None:
    """A blank query skips embedding and returns no hits."""
    _save(deps, "TOP", vector=_BEST, category=MedCategory.FISH)

    assert search_recipes(query="  ") == []
