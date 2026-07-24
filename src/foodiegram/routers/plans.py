import json
import logging
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from foodiegram.api_models import (
    AisleGroupOut,
    CategoryStatusOut,
    GapSuggestion,
    MealUpsert,
    PlannedMealOut,
    PlanResponse,
    RecipeSummary,
    ShoppingItemOut,
)
from foodiegram.app.plan_week import (
    WeekPlanView,
    build_shopping_list,
    build_week_plan_view,
)
from foodiegram.deps import DepsDep

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/plans")

# Static aisle map ships with the repo (Phase 5.2); absent → everything is "altro".
_AISLES_PATH = Path("data/aisles.json")

_NOT_MONDAY = "week_start must be a Monday"


def _load_aisles() -> dict[str, str]:
    """Load the canonical-name → aisle map, or an empty map if it is absent."""
    if not _AISLES_PATH.exists():
        return {}
    raw = json.loads(_AISLES_PATH.read_text(encoding="utf-8"))
    return {str(key): str(value) for key, value in raw.items()}


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


@router.put("/{week_start}/meals")
async def upsert_meal(
    week_start: date,
    body: MealUpsert,
    deps: DepsDep,
) -> PlanResponse:
    """Insert or replace the meal in a (day, slot); return the updated plan."""
    try:
        deps.plans.upsert_meal(
            week_start=week_start,
            day=body.day,
            meal=body.meal,
            recipe_code=body.recipe_code,
            portions=body.portions,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=_NOT_MONDAY) from exc
    return _to_response(
        build_week_plan_view(
            week_start=week_start,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        ),
    )


@router.delete("/{week_start}/meals/{meal_id}")
async def delete_meal(week_start: date, meal_id: int, deps: DepsDep) -> PlanResponse:
    """Remove a meal slot; return the updated plan, or 404 if it was absent."""
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
