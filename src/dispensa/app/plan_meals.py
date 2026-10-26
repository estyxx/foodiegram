import logging
from typing import TYPE_CHECKING, Literal

from dispensa.app.plan_week import WeekPlanView, build_week_plan_view
from dispensa.app.save_custom_recipe import save_custom_recipe
from dispensa.domain.errors import MealNotFoundError, RecipeNotFoundError
from dispensa.domain.planning import (
    PlannedMeal,
    WeekPlan,
    check_meal_slot,
    check_portions,
)

if TYPE_CHECKING:
    from datetime import date

    from dispensa.storage.plans_db import PlanRepository
    from dispensa.storage.recipes_db import RecipeRepository
    from dispensa.storage.targets_db import TargetRepository
    from dispensa.storage.user_state_db import UserStateRepository

logger = logging.getLogger(__name__)


def _occupied_slot(
    *,
    week_start: date,
    day: date,
    meal: Literal["lunch", "dinner"],
    plans: PlanRepository,
) -> PlannedMeal:
    """Return the meal in (day, slot), or raise MealNotFoundError if it is empty."""
    plan = plans.get(week_start) or WeekPlan(week_start=week_start)
    planned = plan.meal_at(day, meal)
    if planned is None:
        msg = f"No meal is planned for {meal} on {day.isoformat()}"
        raise MealNotFoundError(msg)
    return planned


def set_meal(
    *,
    week_start: date,
    day: date,
    meal: Literal["lunch", "dinner"],
    recipe_code: str,
    portions: int,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Put a saved recipe in the (day, slot), replacing any meal there.

    Raises ValueError for a bad week, day or portions and RecipeNotFoundError
    for an unknown code, both before anything is written.
    """
    check_meal_slot(week_start=week_start, day=day)
    check_portions(portions)
    if not recipes.exists(recipe_code):
        msg = f"Recipe {recipe_code!r} not found"
        raise RecipeNotFoundError(msg)
    plans.upsert_meal(
        week_start=week_start,
        day=day,
        meal=meal,
        recipe_code=recipe_code,
        portions=portions,
    )
    return build_week_plan_view(
        week_start=week_start,
        recipes=recipes,
        plans=plans,
        targets=targets,
        user_state=user_state,
    )


def set_draft_meal(
    draft: dict[str, object],
    *,
    week_start: date,
    day: date,
    meal: Literal["lunch", "dinner"],
    portions: int,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Save a draft as a MANUAL recipe, then slot it (D23).

    The slot is checked first so a bad week or day never leaves an orphan
    recipe behind; the balance engine then works off the saved recipe.
    """
    check_meal_slot(week_start=week_start, day=day)
    check_portions(portions)
    saved = save_custom_recipe(draft, recipes=recipes)
    logger.info("Saved draft %s for %s on %s", saved.code, meal, day.isoformat())
    return set_meal(
        week_start=week_start,
        day=day,
        meal=meal,
        recipe_code=saved.code,
        portions=portions,
        recipes=recipes,
        plans=plans,
        targets=targets,
        user_state=user_state,
    )


def clear_meal(
    *,
    week_start: date,
    day: date,
    meal: Literal["lunch", "dinner"],
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Empty the (day, slot); raise MealNotFoundError if it already was."""
    check_meal_slot(week_start=week_start, day=day)
    planned = _occupied_slot(week_start=week_start, day=day, meal=meal, plans=plans)
    if planned.id is None or not plans.delete_meal(week_start, planned.id):
        msg = f"No meal is planned for {meal} on {day.isoformat()}"
        raise MealNotFoundError(msg)
    return build_week_plan_view(
        week_start=week_start,
        recipes=recipes,
        plans=plans,
        targets=targets,
        user_state=user_state,
    )


def set_portions(
    *,
    week_start: date,
    day: date,
    meal: Literal["lunch", "dinner"],
    portions: int,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Change the portions of the meal already in (day, slot), keeping its recipe."""
    check_meal_slot(week_start=week_start, day=day)
    check_portions(portions)
    planned = _occupied_slot(week_start=week_start, day=day, meal=meal, plans=plans)
    return set_meal(
        week_start=week_start,
        day=day,
        meal=meal,
        recipe_code=planned.recipe_code,
        portions=portions,
        recipes=recipes,
        plans=plans,
        targets=targets,
        user_state=user_state,
    )
