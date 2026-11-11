import json
import logging
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from dispensa.api_models import (
    AisleGroupOut,
    CategoryStatusOut,
    GapSuggestion,
    MealCreate,
    MealMove,
    MealUpdate,
    PlannedMealOut,
    PlanResponse,
    RecipeSummary,
    ShoppingItemOut,
)
from dispensa.app.plan_meals import add_meal, move_meal, replace_meal
from dispensa.app.plan_week import (
    WeekPlanView,
    build_shopping_list,
    build_week_plan_view,
)
from dispensa.deps import DepsDep
from dispensa.domain.aisles import DEFAULT_AISLES
from dispensa.domain.errors import MealNotFoundError, RecipeNotFoundError
from dispensa.domain.synonyms import canonical_term

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plans")

# A starter aisle map ships with the repo (15.2); the owner can extend it with
# an optional data/aisles.json, overlaid on top. Unmapped names fall to "altro".
_AISLES_PATH = Path("data/aisles.json")

_NOT_MONDAY = "week_start must be a Monday"


def _load_aisles() -> dict[str, str]:
    """Return the starter aisle map, overlaid with an optional data/aisles.json.

    The owner's file keys are canonicalised the same way, so they line up with
    the names the shopping list produces whichever synonym they are written as.
    """
    aisles = dict(DEFAULT_AISLES)
    if _AISLES_PATH.exists():
        raw = json.loads(_AISLES_PATH.read_text(encoding="utf-8"))
        for key, value in raw.items():
            aisles[canonical_term(str(key))] = str(value)
    return aisles


def _to_response(view: WeekPlanView) -> PlanResponse:
    """Shape the app-layer view into the flat API payload."""
    return PlanResponse(
        week_start=view.plan.week_start,
        meals=[
            PlannedMealOut(
                id=meal.id,
                day=meal.day,
                meal=meal.meal,
                recipe_code=meal.recipe_code,
                portions=meal.portions,
            )
            for meal in view.plan.meals
        ],
        balance=[
            CategoryStatusOut(
                category=status.category.value,
                planned=status.planned,
                min_servings=status.target.min_servings,
                max_servings=status.target.max_servings,
                state=status.state,
            )
            for status in view.balance
        ],
        oily_fish=view.oily_fish,
        suggestions=[
            GapSuggestion(
                category=category.value,
                recipes=[RecipeSummary.from_recipe(recipe) for recipe in recipes],
            )
            for category, recipes in view.suggestions.items()
        ],
    )


@router.get("/{week_start}")
async def get_plan(week_start: date, deps: DepsDep) -> PlanResponse:
    """Return the plan, its balance, and gap suggestions in one payload."""
    try:
        view = build_week_plan_view(
            week_start=week_start,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_NOT_MONDAY) from exc
    return _to_response(view)


@router.post("/{week_start}/meals")
async def create_meal(
    week_start: date,
    body: MealCreate,
    deps: DepsDep,
) -> PlanResponse:
    """Add a dish to a (day, slot) beside any already there; return the plan."""
    try:
        view = add_meal(
            week_start=week_start,
            day=body.day,
            meal=body.meal,
            recipe_code=body.recipe_code,
            portions=body.portions,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        )
    except RecipeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(view)


@router.put("/{week_start}/meals/{meal_id}")
async def update_meal(
    week_start: date,
    meal_id: int,
    body: MealUpdate,
    deps: DepsDep,
) -> PlanResponse:
    """Swap the recipe or portions of one planned dish; return the plan."""
    try:
        view = replace_meal(
            week_start=week_start,
            meal_id=meal_id,
            recipe_code=body.recipe_code,
            portions=body.portions,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        )
    except (MealNotFoundError, RecipeNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(view)


@router.post("/{week_start}/meals/{meal_id}/move")
async def move_planned_meal(
    week_start: date,
    meal_id: int,
    body: MealMove,
    deps: DepsDep,
) -> PlanResponse:
    """Move one planned dish to (day, slot) in any week; return this week's plan."""
    try:
        view = move_meal(
            week_start=week_start,
            meal_id=meal_id,
            day=body.day,
            meal=body.meal,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        )
    except MealNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_response(view)


@router.delete("/{week_start}/meals/{meal_id}")
async def delete_meal(week_start: date, meal_id: int, deps: DepsDep) -> PlanResponse:
    """Remove one planned dish; return the updated plan, or 404 if it was absent."""
    if not deps.plans.delete_meal(week_start, meal_id):
        msg = f"Meal {meal_id} not found in week {week_start.isoformat()}"
        raise HTTPException(status_code=404, detail=msg)
    return _to_response(
        build_week_plan_view(
            week_start=week_start,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        ),
    )


@router.get("/{week_start}/shopping-list")
async def get_shopping_list(week_start: date, deps: DepsDep) -> list[AisleGroupOut]:
    """Return the week's not-in-pantry ingredients grouped by aisle."""
    try:
        groups = build_shopping_list(
            week_start=week_start,
            recipes=deps.recipes,
            plans=deps.plans,
            pantry=deps.pantry,
            aisles=_load_aisles(),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_NOT_MONDAY) from exc
    return [
        AisleGroupOut(
            aisle=group.aisle,
            items=[
                ShoppingItemOut(name=item.name, raw_lines=item.raw_lines)
                for item in group.items
            ],
        )
        for group in groups
    ]
