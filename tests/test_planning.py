from collections.abc import Sequence
from datetime import date

import pytest
from pydantic import ValidationError

from foodiegram.domain.enums import MedCategory
from foodiegram.domain.models import CategoryServing, Recipe
from foodiegram.domain.planning import (
    CategoryStatus,
    CategoryTarget,
    PlannedMeal,
    WeekPlan,
    gap_suggestions,
    oily_fish_count,
    week_balance,
)

_MONDAY = date(2024, 1, 1)
_TUESDAY = date(2024, 1, 2)
_FISH_TARGET = CategoryTarget(category=MedCategory.FISH, min_servings=2, max_servings=3)
_LEGUMES_SERVINGS = 2.0


def _recipe(
    code: str,
    *,
    categories: Sequence[CategoryServing] = (),
    is_recipe: bool = True,
    archived: bool = False,
    confidence: float = 0.8,
) -> Recipe:
    """Build a recipe carrying the given Mediterranean-category servings."""
    return Recipe(
        code=code,
        pk="1",
        post_url=f"https://instagram.com/p/{code}/",
        caption=None,
        title=f"Recipe {code}",
        ingredients=["water"],
        instructions=["cook"],
        mediterranean_categories=list(categories),
        is_recipe=is_recipe,
        archived=archived,
        confidence=confidence,
    )


def _fish_plan(slots: int) -> WeekPlan:
    """Build a plan with `slots` lunch meals, each a one-serving fish recipe."""
    recipe_codes = [f"F{i}" for i in range(slots)]
    meals = tuple(
        PlannedMeal(day=_MONDAY, meal="lunch", recipe_code=code) for code in recipe_codes
    )
    return WeekPlan(week_start=_MONDAY, meals=meals)


def _fish_recipes(slots: int) -> dict[str, Recipe]:
    """Recipes for _fish_plan: each contributes one fish serving."""
    return {
        f"F{i}": _recipe(
            f"F{i}",
            categories=[CategoryServing(category=MedCategory.FISH)],
        )
        for i in range(slots)
    }


def test_week_start_must_be_monday() -> None:
    """WeekPlan accepts a Monday and rejects any other weekday."""
    assert WeekPlan(week_start=_MONDAY).week_start == _MONDAY
    with pytest.raises(ValidationError):
        WeekPlan(week_start=_TUESDAY)


def test_multi_category_recipe_and_portions_never_affect_balance() -> None:
    """A slot counts each category once; portions do not scale the balance."""
    recipe = _recipe(
        "ABC",
        categories=[
            CategoryServing(category=MedCategory.FISH),
            CategoryServing(category=MedCategory.LEGUMES, servings=_LEGUMES_SERVINGS),
        ],
    )
    plan = WeekPlan(
        week_start=_MONDAY,
        meals=(PlannedMeal(day=_MONDAY, meal="lunch", recipe_code="ABC", portions=6),),
    )
    targets = (
        _FISH_TARGET,
        CategoryTarget(category=MedCategory.LEGUMES, min_servings=2, max_servings=3),
    )

    statuses = {s.category: s for s in week_balance(plan, {"ABC": recipe}, targets)}
    assert statuses[MedCategory.FISH].planned == 1.0
    assert statuses[MedCategory.LEGUMES].planned == _LEGUMES_SERVINGS


def test_unknown_recipe_codes_are_skipped() -> None:
    """Meals whose recipe code is absent contribute nothing."""
    plan = WeekPlan(
        week_start=_MONDAY,
        meals=(PlannedMeal(day=_MONDAY, meal="lunch", recipe_code="MISSING"),),
    )
    statuses = week_balance(plan, {}, (_FISH_TARGET,))
    assert statuses[0].planned == 0.0
    assert statuses[0].state == "under"


@pytest.mark.parametrize(
    ("slots", "expected"),
    [(0, "under"), (1, "under"), (2, "ok"), (3, "ok"), (4, "over")],
)
def test_balance_state_boundaries(slots: int, expected: str) -> None:
    """State is over above max, ok at/above min, under below min (min=2, max=3)."""
    statuses = week_balance(_fish_plan(slots), _fish_recipes(slots), (_FISH_TARGET,))
    assert statuses[0].planned == float(slots)
    assert statuses[0].state == expected


def test_zero_min_target_is_ok_at_zero() -> None:
    """A category with min 0 reads ok when nothing is planned."""
    target = CategoryTarget(
        category=MedCategory.PROCESSED_MEAT,
        min_servings=0,
        max_servings=1,
    )
    statuses = week_balance(WeekPlan(week_start=_MONDAY), {}, (target,))
    assert statuses[0].state == "ok"


def test_oily_fish_count_sums_only_oily_servings() -> None:
    """Only servings flagged oily contribute; each slot counts once."""
    oily = _recipe(
        "OILY",
        categories=[CategoryServing(category=MedCategory.FISH, is_oily_fish=True)],
    )
    white = _recipe(
        "WHITE",
        categories=[CategoryServing(category=MedCategory.FISH)],
    )
    plan = WeekPlan(
        week_start=_MONDAY,
        meals=(
            PlannedMeal(day=_MONDAY, meal="lunch", recipe_code="OILY", portions=4),
            PlannedMeal(day=_MONDAY, meal="dinner", recipe_code="WHITE"),
        ),
    )
    assert oily_fish_count(plan, {"OILY": oily, "WHITE": white}) == 1.0


def test_gap_suggestions_ranks_and_filters() -> None:
    """Suggestions rank by confidence then favourites, excluding ineligible recipes."""
    fish = [CategoryServing(category=MedCategory.FISH)]
    candidates = [
        _recipe("F1", categories=fish, confidence=0.9),
        _recipe("F2", categories=fish, confidence=0.8),
        _recipe("F3", categories=fish, confidence=0.8),
        _recipe("ARCH", categories=fish, confidence=0.95, archived=True),
        _recipe("NOTR", categories=fish, confidence=0.99, is_recipe=False),
        _recipe("PLAN", categories=fish, confidence=0.99),
        _recipe("NOFISH", confidence=0.99),
    ]
    statuses = [
        CategoryStatus(
            category=MedCategory.FISH,
            planned=0.0,
            target=_FISH_TARGET,
            state="under",
        ),
    ]

    result = gap_suggestions(
        statuses,
        candidates,
        planned_codes=frozenset({"PLAN"}),
        favourite_codes=frozenset({"F2"}),
    )

    assert [r.code for r in result[MedCategory.FISH]] == ["F1", "F2", "F3"]


def test_gap_suggestions_skips_non_under_categories() -> None:
    """Only under-target categories receive suggestions."""
    statuses = [
        CategoryStatus(
            category=MedCategory.FISH,
            planned=3.0,
            target=_FISH_TARGET,
            state="ok",
        ),
    ]
    result = gap_suggestions(statuses, [])
    assert result == {}
