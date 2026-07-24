from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from foodiegram.domain.enums import MedCategory
from foodiegram.domain.models import Recipe
from foodiegram.domain.planning import (
    CategoryStatus,
    WeekPlan,
    gap_suggestions,
    oily_fish_count,
    week_balance,
)
from foodiegram.domain.shopping import shopping_list

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import date

    from foodiegram.domain.shopping import AisleGroup
    from foodiegram.storage.pantry_db import PantryRepository
    from foodiegram.storage.plans_db import PlanRepository
    from foodiegram.storage.recipes_db import RecipeRepository
    from foodiegram.storage.targets_db import TargetRepository
    from foodiegram.storage.user_state_db import UserStateRepository


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
