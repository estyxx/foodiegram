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


def _slot_dishes(
    *,
    week_start: date,
    day: date,
    meal: Literal["lunch", "dinner"],
    plans: PlanRepository,
) -> tuple[PlannedMeal, ...]:
    """Return the dishes in (day, slot), or raise MealNotFoundError if it is empty."""
    plan = plans.get(week_start) or WeekPlan(week_start=week_start)
    dishes = plan.meals_at(day, meal)
    if not dishes:
        msg = f"No meal is planned for {meal} on {day.isoformat()}"
        raise MealNotFoundError(msg)
    return dishes


def _pick_dish(
    dishes: tuple[PlannedMeal, ...],
    *,
    recipe_code: str | None,
) -> PlannedMeal:
    """Return the dish for recipe_code, or the only dish when no code is given.

    Without a code, a slot holding several dishes is ambiguous; the message
    lists their codes so a client or a model can retry with one.
    """
    if recipe_code is None:
        if len(dishes) == 1:
            return dishes[0]
        codes = ", ".join(dish.recipe_code for dish in dishes)
        msg = f"This slot holds several dishes ({codes}); name one by its code"
        raise ValueError(msg)
    for dish in dishes:
        if dish.recipe_code == recipe_code:
            return dish
    first = dishes[0]
    msg = (
        f"Recipe {recipe_code!r} is not planned for {first.meal} "
        f"on {first.day.isoformat()}"
    )
    raise MealNotFoundError(msg)


def _week_view(
    *,
    week_start: date,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Rebuild the week payload after a write."""
    return build_week_plan_view(
        week_start=week_start,
        recipes=recipes,
        plans=plans,
        targets=targets,
        user_state=user_state,
    )


def add_meal(
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
    """Add a saved recipe to the (day, slot), next to any dishes already there.

    Adding a recipe the slot already holds only updates its portions (D34).
    Raises ValueError for a bad week, day or portions and RecipeNotFoundError
    for an unknown code, both before anything is written.
    """
    check_meal_slot(week_start=week_start, day=day)
    check_portions(portions)
    if not recipes.exists(recipe_code):
        msg = f"Recipe {recipe_code!r} not found"
        raise RecipeNotFoundError(msg)
    plans.add_meal(
        week_start=week_start,
        day=day,
        meal=meal,
        recipe_code=recipe_code,
        portions=portions,
    )
    return _week_view(
        week_start=week_start,
        recipes=recipes,
        plans=plans,
        targets=targets,
        user_state=user_state,
    )


def add_draft_meal(
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
    """Save a draft as a MANUAL recipe, then add it to the slot (D23).

    The slot is checked first so a bad week or day never leaves an orphan
    recipe behind; the balance engine then works off the saved recipe.
    """
    check_meal_slot(week_start=week_start, day=day)
    check_portions(portions)
    saved = save_custom_recipe(draft, recipes=recipes)
    logger.info("Saved draft %s for %s on %s", saved.code, meal, day.isoformat())
    return add_meal(
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


def replace_meal(
    *,
    week_start: date,
    meal_id: int,
    recipe_code: str,
    portions: int,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Swap the recipe and portions of one planned dish, keeping its slot.

    Raises MealNotFoundError for an unknown dish, RecipeNotFoundError for an
    unknown code, and ValueError for bad portions or a recipe another dish in
    the same slot already is.
    """
    check_portions(portions)
    if not recipes.exists(recipe_code):
        msg = f"Recipe {recipe_code!r} not found"
        raise RecipeNotFoundError(msg)
    plan = plans.get(week_start) or WeekPlan(week_start=week_start)
    current = next((dish for dish in plan.meals if dish.id == meal_id), None)
    if current is None:
        msg = f"Meal {meal_id} not found in week {week_start.isoformat()}"
        raise MealNotFoundError(msg)
    siblings = plan.meals_at(current.day, current.meal)
    if any(d.recipe_code == recipe_code and d.id != meal_id for d in siblings):
        msg = f"Recipe {recipe_code!r} is already in this slot"
        raise ValueError(msg)
    updated = plans.update_meal(
        week_start,
        meal_id,
        recipe_code=recipe_code,
        portions=portions,
    )
    if updated is None:
        msg = f"Meal {meal_id} not found in week {week_start.isoformat()}"
        raise MealNotFoundError(msg)
    return _week_view(
        week_start=week_start,
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
    recipe_code: str | None,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Remove one dish from the (day, slot), or every dish when no code is given.

    Raises MealNotFoundError if the slot is empty or lacks that recipe.
    """
    check_meal_slot(week_start=week_start, day=day)
    dishes = _slot_dishes(week_start=week_start, day=day, meal=meal, plans=plans)
    doomed = (
        dishes if recipe_code is None else (_pick_dish(dishes, recipe_code=recipe_code),)
    )
    for dish in doomed:
        if dish.id is None or not plans.delete_meal(week_start, dish.id):
            msg = f"No meal is planned for {meal} on {day.isoformat()}"
            raise MealNotFoundError(msg)
    return _week_view(
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
    recipe_code: str | None,
    portions: int,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Change the portions of one dish in (day, slot), keeping its recipe.

    recipe_code may be omitted only when the slot holds a single dish.
    """
    check_meal_slot(week_start=week_start, day=day)
    check_portions(portions)
    dishes = _slot_dishes(week_start=week_start, day=day, meal=meal, plans=plans)
    dish = _pick_dish(dishes, recipe_code=recipe_code)
    return add_meal(
        week_start=week_start,
        day=day,
        meal=meal,
        recipe_code=dish.recipe_code,
        portions=portions,
        recipes=recipes,
        plans=plans,
        targets=targets,
        user_state=user_state,
    )
