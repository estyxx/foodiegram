from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine

from dispensa.app.plan_week import build_planning_context
from dispensa.domain.enums import MedCategory
from dispensa.domain.models import CategoryServing, Recipe
from dispensa.domain.pantry import PantryItem
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository

_MONDAY = date(2024, 1, 1)
_TUESDAY = date(2024, 1, 2)
_SEEDED_TARGETS = 8


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


def test_planning_context_bundles_plan_targets_pantry_favourites(
    db_engine: Engine,
) -> None:
    """One call returns meals (with titles), targets, pantry, favourites and balance."""
    recipes = RecipeRepository(db_engine)
    plans = PlanRepository(db_engine)
    pantry = PantryRepository(db_engine)
    targets = TargetRepository(db_engine)
    user_state = UserStateRepository(db_engine)

    recipes.save(_recipe("FISH1", category=MedCategory.FISH))
    recipes.save(_recipe("LEG1", category=MedCategory.LEGUMES))
    plans.upsert_meal(
        week_start=_MONDAY,
        day=_MONDAY,
        meal="dinner",
        recipe_code="FISH1",
        portions=2,
    )
    pantry.add(PantryItem(name="olive oil", kind="staple"))
    user_state.set_favorite("LEG1", is_favorite=True)

    context = build_planning_context(
        week_start=_MONDAY,
        recipes=recipes,
        plans=plans,
        targets=targets,
        pantry=pantry,
        user_state=user_state,
    )

    assert [meal.recipe_code for meal in context.meals] == ["FISH1"]
    assert context.meals[0].title == "Recipe FISH1"
    assert len(context.targets) == _SEEDED_TARGETS
    assert [item.name for item in context.pantry] == ["olive oil"]
    assert context.favourite_codes == ("LEG1",)
    fish = next(s for s in context.week.balance if s.category is MedCategory.FISH)
    assert fish.planned == 1.0


def test_planning_context_rejects_a_non_monday(db_engine: Engine) -> None:
    """A non-Monday week_start raises, matching build_week_plan_view."""
    with pytest.raises(ValidationError):
        build_planning_context(
            week_start=_TUESDAY,
            recipes=RecipeRepository(db_engine),
            plans=PlanRepository(db_engine),
            targets=TargetRepository(db_engine),
            pantry=PantryRepository(db_engine),
            user_state=UserStateRepository(db_engine),
        )
