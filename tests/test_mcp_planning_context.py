from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import Engine

from dispensa.deps import Deps
from dispensa.domain.enums import MedCategory
from dispensa.domain.models import CategoryServing, Recipe
from dispensa.domain.pantry import PantryItem
from dispensa.mcp_server.server import get_planning_context
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository

_MONDAY = date(2024, 1, 1)
_SEEDED_TARGETS = 8


def _deps(engine: Engine) -> Deps:
    """Wire repositories for MCP tool tests."""
    return Deps(
        recipes=RecipeRepository(engine),
        extractions=ExtractionRepository(engine),
        user_state=UserStateRepository(engine),
        plans=PlanRepository(engine),
        pantry=PantryRepository(engine),
        targets=TargetRepository(engine),
    )


def _recipe(code: str, *, category: MedCategory) -> Recipe:
    """Build a minimal one-serving recipe in a single Mediterranean category."""
    return Recipe(
        code=code,
        pk=None,
        post_url=None,
        caption=None,
        title=f"Recipe {code}",
        ingredients=["something"],
        instructions=["do it"],
        mediterranean_categories=[CategoryServing(category=category)],
    )


def test_get_planning_context_returns_one_payload(engine: Engine) -> None:
    """The tool bundles meals, balance, targets, pantry and favourites in one dict."""
    deps = _deps(engine)
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    deps.recipes.save(_recipe("LEG1", category=MedCategory.LEGUMES))
    deps.plans.upsert_meal(
        week_start=_MONDAY,
        day=_MONDAY,
        meal="dinner",
        recipe_code="FISH1",
        portions=2,
    )
    deps.pantry.add(PantryItem(name="olive oil", kind="staple"))
    deps.user_state.set_favorite("LEG1", is_favorite=True)

    with patch("dispensa.mcp_server.server._deps", return_value=deps):
        result = get_planning_context(week_start="2024-01-01")

    assert result["week_start"] == "2024-01-01"
    assert result["meals"][0]["recipe_code"] == "FISH1"
    assert result["meals"][0]["title"] == "Recipe FISH1"
    assert len(result["targets"]) == _SEEDED_TARGETS
    assert result["favourite_codes"] == ["LEG1"]
    assert result["pantry"][0]["name"] == "olive oil"
    assert "oily_fish" in result
    assert isinstance(result["suggestions"], list)
    fish = next(s for s in result["balance"] if s["category"] == MedCategory.FISH.value)
    assert fish["planned"] == 1.0


def test_get_planning_context_non_monday_raises(engine: Engine) -> None:
    """A non-Monday week_start is a clear ValueError, not a pydantic dump."""
    deps = _deps(engine)
    with (
        patch("dispensa.mcp_server.server._deps", return_value=deps),
        pytest.raises(ValueError, match="Monday"),
    ):
        get_planning_context(week_start="2024-01-02")


def test_get_planning_context_bad_date_raises(engine: Engine) -> None:
    """A malformed week_start is rejected before any repository read."""
    deps = _deps(engine)
    with (
        patch("dispensa.mcp_server.server._deps", return_value=deps),
        pytest.raises(ValueError, match="ISO date"),
    ):
        get_planning_context(week_start="not-a-date")
