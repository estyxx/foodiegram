from unittest.mock import patch

from sqlalchemy import Engine

from foodiegram.deps import Deps
from foodiegram.mcp_server.server import get_recipe
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.pantry_db import PantryRepository
from foodiegram.storage.plans_db import PlanRepository
from foodiegram.storage.recipes_db import RecipeRepository
from foodiegram.storage.targets_db import TargetRepository
from foodiegram.storage.user_state_db import UserStateRepository
from tests.test_storage_db import _full_recipe

_MED_CATEGORIES = 2


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


def test_get_recipe_returns_full_detail_with_ingredients_and_instructions(
    engine: Engine,
) -> None:
    """get_recipe returns stored ingredients and instructions plus summary fields."""
    recipe = _full_recipe()
    RecipeRepository(engine).save(recipe)
    deps = _deps(engine)

    with patch("foodiegram.mcp_server.server._deps", return_value=deps):
        result = get_recipe(code=recipe.code)

    assert result is not None
    assert result["ingredients"] == ["guanciale", "uova", "pecorino"]
    assert result["instructions"] == ["fry guanciale", "toss with eggs"]
    assert result["code"] == recipe.code
    assert result["title"] == "Carbonara"
    assert result["dish_type"] == "pasta"
    assert result["meal_type"] == "lunch"
    assert result["cuisine_type"] == "italian"
    assert result["proteins"] == ["uova"]
    assert result["total_time"] == "25 minutes"
    assert result["post_url"] == "https://instagram.com/p/ABC/"
    assert result["is_favorite"] is False
    assert result["prep_time"] == "10 minutes"
    assert result["difficulty"] == "medium"
    assert len(result["mediterranean_categories"]) == _MED_CATEGORIES


def test_get_recipe_null_title_serialises_as_null(engine: Engine) -> None:
    """A recipe with no title returns title null, not the string 'None'."""
    recipe = _full_recipe().model_copy(update={"code": "NULLT", "title": None})
    RecipeRepository(engine).save(recipe)
    deps = _deps(engine)

    with patch("foodiegram.mcp_server.server._deps", return_value=deps):
        result = get_recipe(code="NULLT")

    assert result is not None
    assert result["title"] is None


def test_get_recipe_unknown_code_returns_none(engine: Engine) -> None:
    """An unknown code returns None without raising."""
    deps = _deps(engine)

    with patch("foodiegram.mcp_server.server._deps", return_value=deps):
        result = get_recipe(code="UNKNOWN")

    assert result is None
