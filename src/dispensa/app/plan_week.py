from datetime import date
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from dispensa.domain.enums import MedCategory
from dispensa.domain.models import Recipe
from dispensa.domain.pantry import PantryItem
from dispensa.domain.planning import (
    CategoryStatus,
    CategoryTarget,
    WeekPlan,
    gap_suggestions,
    oily_fish_count,
    week_balance,
)
from dispensa.domain.shopping import shopping_list

if TYPE_CHECKING:
    from collections.abc import Mapping

    from dispensa.domain.shopping import AisleGroup
    from dispensa.storage.pantry_db import PantryRepository
    from dispensa.storage.plans_db import PlanRepository
    from dispensa.storage.recipes_db import RecipeRepository
    from dispensa.storage.targets_db import TargetRepository
    from dispensa.storage.user_state_db import UserStateRepository


class WeekPlanView(BaseModel):
    """The whole week payload: plan, graded balance, oily-fish tally, gaps."""

    model_config = ConfigDict(frozen=True)

    plan: WeekPlan
    balance: tuple[CategoryStatus, ...]
    oily_fish: float
    suggestions: dict[MedCategory, tuple[Recipe, ...]]


def build_week_plan_view(
    *,
    week_start: date,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    user_state: UserStateRepository,
) -> WeekPlanView:
    """Assemble the plan, its balance, oily-fish count, and gap suggestions.

    Raises pydantic ValidationError if week_start is not a Monday (no plan yet).
    """
    plan = plans.get(week_start) or WeekPlan(week_start=week_start)
    recipe_map = {recipe.code: recipe for recipe in recipes.list_all()}
    balance = tuple(week_balance(plan, recipe_map, tuple(targets.list_all())))
    planned = frozenset(meal.recipe_code for meal in plan.meals)
    favourites = frozenset(user_state.all_favorites())
    suggestions = gap_suggestions(
        balance,
        list(recipe_map.values()),
        planned_codes=planned,
        favourite_codes=favourites,
    )
    return WeekPlanView(
        plan=plan,
        balance=balance,
        oily_fish=oily_fish_count(plan, recipe_map),
        suggestions={
            category: tuple(recipes_for) for category, recipes_for in suggestions.items()
        },
    )


class PlannedMealView(BaseModel):
    """One planned slot with its recipe title resolved, for the planning payload."""

    model_config = ConfigDict(frozen=True)

    day: date
    meal: Literal["lunch", "dinner"]
    recipe_code: str
    portions: int
    title: str | None


class PlanningContext(BaseModel):
    """Everything a planner needs for one week in a single read."""

    model_config = ConfigDict(frozen=True)

    week: WeekPlanView
    meals: tuple[PlannedMealView, ...]
    targets: tuple[CategoryTarget, ...]
    pantry: tuple[PantryItem, ...]
    favourite_codes: tuple[str, ...]


def build_planning_context(
    *,
    week_start: date,
    recipes: RecipeRepository,
    plans: PlanRepository,
    targets: TargetRepository,
    pantry: PantryRepository,
    user_state: UserStateRepository,
) -> PlanningContext:
    """Assemble the plan, balance, gaps, targets, pantry and favourites for a week.

    Raises pydantic ValidationError if week_start is not a Monday.
    """
    view = build_week_plan_view(
        week_start=week_start,
        recipes=recipes,
        plans=plans,
        targets=targets,
        user_state=user_state,
    )
    titles = {
        code: (found.title if (found := recipes.get(code)) else None)
        for code in {meal.recipe_code for meal in view.plan.meals}
    }
    meals = tuple(
        PlannedMealView(
            day=meal.day,
            meal=meal.meal,
            recipe_code=meal.recipe_code,
            portions=meal.portions,
            title=titles.get(meal.recipe_code),
        )
        for meal in view.plan.meals
    )
    return PlanningContext(
        week=view,
        meals=meals,
        targets=tuple(targets.list_all()),
        pantry=tuple(pantry.list_all()),
        favourite_codes=tuple(sorted(user_state.all_favorites())),
    )


def build_shopping_list(
    *,
    week_start: date,
    recipes: RecipeRepository,
    plans: PlanRepository,
    pantry: PantryRepository,
    aisles: Mapping[str, str],
) -> list[AisleGroup]:
    """Build the week's aisle-grouped shopping list of not-in-pantry items."""
    plan = plans.get(week_start) or WeekPlan(week_start=week_start)
    recipe_map = {recipe.code: recipe for recipe in recipes.list_all()}
    return shopping_list(plan, recipe_map, pantry.list_all(), aisles)
