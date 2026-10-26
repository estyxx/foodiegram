from collections.abc import Generator
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import Engine

from dispensa.api_models import RecipeCreate
from dispensa.deps import Deps
from dispensa.domain.enums import MedCategory, RecipeSource
from dispensa.domain.models import (
    CategoryServing,
    ExtractedCategoryServing,
    Recipe,
)
from dispensa.mcp_server.write_tools import (
    clear_meal,
    set_meal,
    set_portions,
)
from dispensa.storage.exercise_log_db import ExerciseLogRepository
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository

_MONDAY = "2024-01-01"
_TUESDAY = "2024-01-02"
_NEXT_MONDAY = "2024-01-08"
_THREE_PORTIONS = 3


@pytest.fixture
def deps(db_engine: Engine) -> Generator[Deps]:
    """Wire repositories and point the write tools at them."""
    wired = Deps(
        recipes=RecipeRepository(db_engine),
        extractions=ExtractionRepository(db_engine),
        user_state=UserStateRepository(db_engine),
        plans=PlanRepository(db_engine),
        pantry=PantryRepository(db_engine),
        targets=TargetRepository(db_engine),
        exercise_log=ExerciseLogRepository(db_engine),
    )
    with patch("dispensa.mcp_server.write_tools.get_deps", return_value=wired):
        yield wired


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


def _draft(*, inspired_by: tuple[str, ...] = ()) -> RecipeCreate:
    """Build a hand-authored legumes draft, the shape a model sends."""
    return RecipeCreate(
        title="Pasta e ceci della nonna",
        ingredients=["200g ceci", "160g pasta"],
        instructions=[],
        mediterranean_categories=[ExtractedCategoryServing(category="legumes")],
        inspired_by=list(inspired_by),
    )


def _planned(result: dict[str, object], category: MedCategory) -> object:
    """Return the planned servings for one category in a write tool's response."""
    balance = result["balance"]
    assert isinstance(balance, list)
    return next(row["planned"] for row in balance if row["category"] == category.value)


# --- set_meal ---------------------------------------------------------------


def test_set_meal_by_code_returns_the_fresh_week(deps: Deps) -> None:
    """Slotting a code returns meals with titles, the moved balance and oily fish."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))

    result = set_meal(week_start=_MONDAY, day=_TUESDAY, slot="dinner", code="FISH1")

    assert result["week_start"] == _MONDAY
    assert result["meals"] == [
        {
            "day": _TUESDAY,
            "meal": "dinner",
            "recipe_code": "FISH1",
            "portions": 2,
            "title": "Recipe FISH1",
        },
    ]
    assert _planned(result, MedCategory.FISH) == 1.0
    assert "oily_fish" in result
    assert "suggestions" in result


def test_set_meal_replaces_the_slot(deps: Deps) -> None:
    """A second set_meal on the same slot replaces the meal rather than adding one."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    deps.recipes.save(_recipe("LEG1", category=MedCategory.LEGUMES))
    set_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="FISH1")

    result = set_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="LEG1")

    assert [meal["recipe_code"] for meal in result["meals"]] == ["LEG1"]
    assert _planned(result, MedCategory.FISH) == 0.0
    assert _planned(result, MedCategory.LEGUMES) == 1.0


def test_set_meal_with_a_draft_saves_a_manual_recipe_then_slots_it(
    deps: Deps,
) -> None:
    """D23: the draft becomes a MANUAL recipe and the balance counts its category."""
    result = set_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", draft=_draft())

    (meal,) = result["meals"]
    assert meal["recipe_code"].startswith("m-pasta-e-ceci-della-nonna-")
    assert meal["title"] == "Pasta e ceci della nonna"
    assert _planned(result, MedCategory.LEGUMES) == 1.0
    saved = deps.recipes.get(meal["recipe_code"])
    assert saved is not None
    assert saved.source is RecipeSource.MANUAL
    assert [serving.source for serving in saved.mediterranean_categories] == [
        "manual",
    ]


def test_set_meal_needs_exactly_one_of_code_or_draft(deps: Deps) -> None:
    """Neither or both of code/draft is rejected with an actionable message."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    with pytest.raises(ValueError, match="exactly one of code"):
        set_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch")
    with pytest.raises(ValueError, match="exactly one of code"):
        set_meal(
            week_start=_MONDAY,
            day=_MONDAY,
            slot="lunch",
            code="FISH1",
            draft=_draft(),
        )
    assert deps.plans.get(date.fromisoformat(_MONDAY)) is None


def test_set_meal_unknown_code_raises_and_writes_nothing(deps: Deps) -> None:
    """A bad code is a ValueError pointing at search_recipes; no slot is created."""
    with pytest.raises(ValueError, match=r"'NOPE' not found.*search_recipes"):
        set_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="NOPE")
    assert deps.plans.get(date.fromisoformat(_MONDAY)) is None


def test_set_meal_non_monday_week_start_raises(deps: Deps) -> None:
    """A non-Monday week_start is a ValueError naming the date."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    with pytest.raises(ValueError, match="2024-01-02 is not a Monday"):
        set_meal(week_start=_TUESDAY, day=_TUESDAY, slot="lunch", code="FISH1")


def test_set_meal_day_outside_the_week_raises(deps: Deps) -> None:
    """A day from another week is rejected with the valid range."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    with pytest.raises(ValueError, match=r"outside the week 2024-01-01\.\.2024-01-07"):
        set_meal(week_start=_MONDAY, day=_NEXT_MONDAY, slot="lunch", code="FISH1")


def test_set_meal_malformed_date_names_the_argument(deps: Deps) -> None:
    """A malformed day says which argument was wrong."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    with pytest.raises(ValueError, match="day must be an ISO date"):
        set_meal(week_start=_MONDAY, day="tuesday", slot="lunch", code="FISH1")


def test_set_meal_draft_with_a_bad_week_saves_no_recipe(deps: Deps) -> None:
    """The slot is checked before the draft is saved, so no orphan recipe is left."""
    with pytest.raises(ValueError, match="not a Monday"):
        set_meal(week_start=_TUESDAY, day=_TUESDAY, slot="lunch", draft=_draft())
    assert deps.recipes.list_all() == []


# --- clear_meal / set_portions ------------------------------------------------


def test_clear_meal_empties_the_slot_and_the_balance(deps: Deps) -> None:
    """Clearing a slot drops the meal and its servings from the balance."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    set_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="FISH1")

    result = clear_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner")

    assert result["meals"] == []
    assert _planned(result, MedCategory.FISH) == 0.0


def test_clear_meal_on_an_empty_slot_raises(deps: Deps) -> None:
    """Clearing a slot that holds nothing is an error, not a silent no-op."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    set_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="FISH1")
    with pytest.raises(ValueError, match="No meal is planned for lunch on 2024-01-01"):
        clear_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch")


def test_set_portions_keeps_the_recipe(deps: Deps) -> None:
    """set_portions changes only the portion count of the meal in the slot."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    set_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="FISH1")

    result = set_portions(
        week_start=_MONDAY,
        day=_MONDAY,
        slot="dinner",
        portions=_THREE_PORTIONS,
    )

    (meal,) = result["meals"]
    assert meal["recipe_code"] == "FISH1"
    assert meal["portions"] == _THREE_PORTIONS
    assert _planned(result, MedCategory.FISH) == 1.0


def test_set_portions_rejects_an_empty_slot_and_zero(deps: Deps) -> None:
    """An empty slot and a portion count below one are both actionable errors."""
    with pytest.raises(ValueError, match="No meal is planned"):
        set_portions(week_start=_MONDAY, day=_MONDAY, slot="lunch", portions=2)
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    set_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="FISH1")
    with pytest.raises(ValueError, match="portions must be at least 1"):
        set_portions(week_start=_MONDAY, day=_MONDAY, slot="lunch", portions=0)
