from collections.abc import Callable, Generator
from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import Engine

from dispensa.api_models import RecipeCreate
from dispensa.app.promotion import promote_version
from dispensa.deps import Deps
from dispensa.domain.enums import MedCategory, RecipeSource
from dispensa.domain.models import (
    CategoryServing,
    ExtractedCategoryServing,
    ExtractedRecipe,
    Extraction,
    Recipe,
)
from dispensa.mcp_server.write_tools import (
    add_meal,
    clear_meal,
    save_recipe,
    set_portions,
    update_recipe,
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
_EDITED_SERVINGS = 4
_EXTRACTED_SERVINGS = 6
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


# --- add_meal ---------------------------------------------------------------


def test_add_meal_by_code_returns_the_fresh_week(deps: Deps) -> None:
    """Slotting a code returns meals with titles, the moved balance and oily fish."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))

    result = add_meal(week_start=_MONDAY, day=_TUESDAY, slot="dinner", code="FISH1")

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


def test_add_meal_keeps_the_dish_already_in_the_slot(deps: Deps) -> None:
    """D34: a second add_meal on the same slot adds a dish beside the first."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    deps.recipes.save(_recipe("LEG1", category=MedCategory.LEGUMES))
    add_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="FISH1")

    result = add_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="LEG1")

    assert [meal["recipe_code"] for meal in result["meals"]] == ["FISH1", "LEG1"]
    assert _planned(result, MedCategory.FISH) == 1.0
    assert _planned(result, MedCategory.LEGUMES) == 1.0


def test_add_meal_twice_with_one_recipe_updates_its_portions(deps: Deps) -> None:
    """Re-adding a recipe the slot already holds never stacks a duplicate."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    add_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="FISH1")

    result = add_meal(
        week_start=_MONDAY,
        day=_MONDAY,
        slot="lunch",
        code="FISH1",
        portions=_THREE_PORTIONS,
    )

    (meal,) = result["meals"]
    assert meal["portions"] == _THREE_PORTIONS
    assert _planned(result, MedCategory.FISH) == 1.0


def test_add_meal_with_a_draft_saves_a_manual_recipe_then_slots_it(
    deps: Deps,
) -> None:
    """D23: the draft becomes a MANUAL recipe and the balance counts its category."""
    result = add_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", draft=_draft())

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


def test_add_meal_needs_exactly_one_of_code_or_draft(deps: Deps) -> None:
    """Neither or both of code/draft is rejected with an actionable message."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    with pytest.raises(ValueError, match="exactly one of code"):
        add_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch")
    with pytest.raises(ValueError, match="exactly one of code"):
        add_meal(
            week_start=_MONDAY,
            day=_MONDAY,
            slot="lunch",
            code="FISH1",
            draft=_draft(),
        )
    assert deps.plans.get(date.fromisoformat(_MONDAY)) is None


def test_add_meal_unknown_code_raises_and_writes_nothing(deps: Deps) -> None:
    """A bad code is a ValueError pointing at search_recipes; no slot is created."""
    with pytest.raises(ValueError, match=r"'NOPE' not found.*search_recipes"):
        add_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="NOPE")
    assert deps.plans.get(date.fromisoformat(_MONDAY)) is None


def test_add_meal_non_monday_week_start_raises(deps: Deps) -> None:
    """A non-Monday week_start is a ValueError naming the date."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    with pytest.raises(ValueError, match="2024-01-02 is not a Monday"):
        add_meal(week_start=_TUESDAY, day=_TUESDAY, slot="lunch", code="FISH1")


def test_add_meal_day_outside_the_week_raises(deps: Deps) -> None:
    """A day from another week is rejected with the valid range."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    with pytest.raises(ValueError, match=r"outside the week 2024-01-01\.\.2024-01-07"):
        add_meal(week_start=_MONDAY, day=_NEXT_MONDAY, slot="lunch", code="FISH1")


def test_add_meal_malformed_date_names_the_argument(deps: Deps) -> None:
    """A malformed day says which argument was wrong."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    with pytest.raises(ValueError, match="day must be an ISO date"):
        add_meal(week_start=_MONDAY, day="tuesday", slot="lunch", code="FISH1")


def test_add_meal_draft_with_a_bad_week_saves_no_recipe(deps: Deps) -> None:
    """The slot is checked before the draft is saved, so no orphan recipe is left."""
    with pytest.raises(ValueError, match="not a Monday"):
        add_meal(week_start=_TUESDAY, day=_TUESDAY, slot="lunch", draft=_draft())
    assert deps.recipes.list_all() == []


# --- clear_meal / set_portions ------------------------------------------------


def test_clear_meal_empties_the_slot_and_the_balance(deps: Deps) -> None:
    """Clearing a slot drops the meal and its servings from the balance."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    add_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="FISH1")

    result = clear_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner")

    assert result["meals"] == []
    assert _planned(result, MedCategory.FISH) == 0.0


def _two_dish_dinner(deps: Deps) -> None:
    """Plan FISH1 and LEG1 together for Monday dinner."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    deps.recipes.save(_recipe("LEG1", category=MedCategory.LEGUMES))
    add_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="FISH1")
    add_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="LEG1")


def test_clear_meal_with_a_code_removes_only_that_dish(deps: Deps) -> None:
    """Naming a dish leaves the rest of the slot in place."""
    _two_dish_dinner(deps)

    result = clear_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="FISH1")

    assert [meal["recipe_code"] for meal in result["meals"]] == ["LEG1"]
    assert _planned(result, MedCategory.FISH) == 0.0


def test_clear_meal_without_a_code_empties_every_dish(deps: Deps) -> None:
    """No code means the whole slot goes."""
    _two_dish_dinner(deps)

    result = clear_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner")

    assert result["meals"] == []


def test_clear_meal_with_a_code_not_in_the_slot_raises(deps: Deps) -> None:
    """A code the slot lacks is an error naming it, and nothing is removed."""
    _two_dish_dinner(deps)
    with pytest.raises(ValueError, match="'NOPE' is not planned for dinner"):
        clear_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="NOPE")
    plan = deps.plans.get(date.fromisoformat(_MONDAY))
    assert plan is not None
    assert len(plan.meals) == len(("FISH1", "LEG1"))


def test_clear_meal_on_an_empty_slot_raises(deps: Deps) -> None:
    """Clearing a slot that holds nothing is an error, not a silent no-op."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    add_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="FISH1")
    with pytest.raises(ValueError, match="No meal is planned for lunch on 2024-01-01"):
        clear_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch")


def test_set_portions_keeps_the_recipe(deps: Deps) -> None:
    """set_portions changes only the portion count of the meal in the slot."""
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    add_meal(week_start=_MONDAY, day=_MONDAY, slot="dinner", code="FISH1")

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


def test_set_portions_names_one_dish_in_a_shared_slot(deps: Deps) -> None:
    """With several dishes the code picks one; without it the error lists them."""
    _two_dish_dinner(deps)
    with pytest.raises(ValueError, match=r"several dishes \(FISH1, LEG1\)"):
        set_portions(week_start=_MONDAY, day=_MONDAY, slot="dinner", portions=4)

    result = set_portions(
        week_start=_MONDAY,
        day=_MONDAY,
        slot="dinner",
        code="LEG1",
        portions=_THREE_PORTIONS,
    )

    portions = {meal["recipe_code"]: meal["portions"] for meal in result["meals"]}
    assert portions == {"FISH1": 2, "LEG1": _THREE_PORTIONS}


def test_set_portions_rejects_an_empty_slot_and_zero(deps: Deps) -> None:
    """An empty slot and a portion count below one are both actionable errors."""
    with pytest.raises(ValueError, match="No meal is planned"):
        set_portions(week_start=_MONDAY, day=_MONDAY, slot="lunch", portions=2)
    deps.recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    add_meal(week_start=_MONDAY, day=_MONDAY, slot="lunch", code="FISH1")
    with pytest.raises(ValueError, match="portions must be at least 1"):
        set_portions(week_start=_MONDAY, day=_MONDAY, slot="lunch", portions=0)


# --- save_recipe / update_recipe ------------------------------------------------


def test_save_recipe_stores_a_manual_recipe_with_inspired_by(deps: Deps) -> None:
    """save_recipe returns the stored detail; inspired_by may name a non-recipe."""
    deps.recipes.save(
        _recipe("POST1", category=MedCategory.LEGUMES).model_copy(
            update={"is_recipe": False},
        ),
    )

    result = save_recipe(draft=_draft(inspired_by=("POST1",)))

    assert result["code"].startswith("m-")
    assert result["source"] == RecipeSource.MANUAL.value
    assert result["inspired_by"] == ["POST1"]
    assert result["ingredients"] == ["200g ceci", "160g pasta"]
    assert deps.recipes.exists(result["code"])


def test_update_recipe_applies_only_the_passed_fields(deps: Deps) -> None:
    """Omitted arguments stay as they were; base_servings becomes user-owned."""
    deps.recipes.save(_recipe("LEG1", category=MedCategory.LEGUMES))
    update_recipe(code="LEG1", user_notes="weeknight winner")

    result = update_recipe(code="LEG1", is_favorite=True, base_servings=4)

    assert result["is_favorite"] is True
    assert result["user_notes"] == "weeknight winner"
    assert result["base_servings"] == _EDITED_SERVINGS
    assert result["edited_fields"] == ["base_servings"]


def test_update_recipe_unknown_code_raises(deps: Deps) -> None:
    """A bad code is a ValueError, not a None return, and writes no user state."""
    with pytest.raises(ValueError, match="'NOPE' not found"):
        update_recipe(code="NOPE", is_favorite=True)
    assert deps.user_state.get("NOPE") is None


def test_update_recipe_edit_survives_promotion(
    deps: Deps,
    make_extracted: Callable[..., ExtractedRecipe],
    make_extraction: Callable[..., Extraction],
) -> None:
    """9.2 invariant: a hand-edited base_servings is never overwritten by promote."""
    deps.recipes.save(_recipe("LEG1", category=MedCategory.LEGUMES))
    update_recipe(code="LEG1", base_servings=_EDITED_SERVINGS)
    payload = make_extracted(title="Re-extracted").model_copy(
        update={"servings": str(_EXTRACTED_SERVINGS)},
    )
    deps.extractions.add(make_extraction(code="LEG1", payload=payload))

    report = promote_version(
        recipes=deps.recipes,
        extractions=deps.extractions,
        version="2",
        dry_run=False,
    )

    promoted = deps.recipes.get("LEG1")
    assert promoted is not None
    assert report.promoted == 1
    assert promoted.title == "Re-extracted"
    assert promoted.base_servings == _EDITED_SERVINGS
