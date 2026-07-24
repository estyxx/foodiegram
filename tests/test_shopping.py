from collections.abc import Sequence
from datetime import date

from foodiegram.domain.models import Recipe
from foodiegram.domain.pantry import PantryItem
from foodiegram.domain.planning import PlannedMeal, WeekPlan
from foodiegram.domain.shopping import shopping_list

_MONDAY = date(2024, 1, 1)
_EXPECTED_RAW_LINES = 2


def _recipe(code: str, ingredients: Sequence[str]) -> Recipe:
    """Build a minimal recipe carrying the given raw ingredient lines."""
    return Recipe(
        code=code,
        pk="1",
        post_url=f"https://instagram.com/p/{code}/",
        caption=None,
        title=f"Recipe {code}",
        ingredients=list(ingredients),
        instructions=["cook"],
    )


def _plan(*codes: str) -> WeekPlan:
    meals = tuple(
        PlannedMeal(day=_MONDAY, meal="lunch", recipe_code=code) for code in codes
    )
    return WeekPlan(week_start=_MONDAY, meals=meals)


def test_missing_ingredients_canonicalised_and_grouped_by_aisle() -> None:
    """Missing lines canonicalise to synonyms and land in the mapped aisles."""
    recipe = _recipe("A", ["200g zucchine", "50g parmigiano", "2 eggs"])
    pantry = [PantryItem(name="eggs", kind="fresh")]
    aisles = {"courgette": "produce", "parmesan": "dairy"}

    groups = shopping_list(_plan("A"), {"A": recipe}, pantry, aisles)

    assert [(g.aisle, [i.name for i in g.items]) for g in groups] == [
        ("dairy", ["parmesan"]),
        ("produce", ["courgette"]),
    ]


def test_unknown_ingredient_falls_back_to_altro() -> None:
    """An ingredient with no aisle mapping is grouped under 'altro'."""
    recipe = _recipe("A", ["1 tsp salt"])

    groups = shopping_list(_plan("A"), {"A": recipe}, [], {})

    assert len(groups) == 1
    assert groups[0].aisle == "altro"
    assert groups[0].items[0].name == "salt"


def test_duplicate_ingredients_dedupe_and_keep_raw_lines() -> None:
    """The same canonical ingredient across meals dedupes, keeping raw lines."""
    plan = _plan("A", "B")
    recipes = {
        "A": _recipe("A", ["200g zucchine"]),
        "B": _recipe("B", ["3 zucchine"]),
    }

    groups = shopping_list(plan, recipes, [], {"courgette": "produce"})

    items = groups[0].items
    assert len(items) == 1
    assert items[0].name == "courgette"
    assert len(items[0].raw_lines) == _EXPECTED_RAW_LINES
    assert items[0].raw_lines == ["200g zucchine", "3 zucchine"]


def test_missing_recipe_codes_are_skipped() -> None:
    """A planned meal whose recipe is absent contributes nothing."""
    groups = shopping_list(_plan("GONE"), {}, [], {})

    assert groups == []
