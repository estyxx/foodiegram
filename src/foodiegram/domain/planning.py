from datetime import date
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, field_validator

from foodiegram.domain.enums import MedCategory

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from foodiegram.domain.models import Recipe

# date.weekday() index for Monday; week plans always start on a Monday.
_MONDAY = 0


class CategoryTarget(BaseModel):
    """Weekly serving target range for one Mediterranean category."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: MedCategory
    min_servings: float
    max_servings: float


# Default weekly targets from the Mediterranean engine table (§2). User-editable
# later; seeded into the targets table when it is empty.
DEFAULT_TARGETS: tuple[CategoryTarget, ...] = (
    CategoryTarget(category=MedCategory.FISH, min_servings=2, max_servings=3),
    CategoryTarget(category=MedCategory.LEGUMES, min_servings=2, max_servings=3),
    CategoryTarget(category=MedCategory.POULTRY, min_servings=1, max_servings=2),
    CategoryTarget(category=MedCategory.EGGS, min_servings=2, max_servings=4),
    CategoryTarget(category=MedCategory.DAIRY, min_servings=0, max_servings=7),
    CategoryTarget(category=MedCategory.RED_MEAT, min_servings=0, max_servings=2),
    CategoryTarget(
        category=MedCategory.PROCESSED_MEAT,
        min_servings=0,
        max_servings=1,
    ),
)


class PlannedMeal(BaseModel):
    """One recipe assigned to a lunch or dinner slot on a given day."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day: date
    meal: Literal["lunch", "dinner"]
    recipe_code: str
    # Portions scale ingredients and the shopping list only — never the balance.
    portions: int = 2


class WeekPlan(BaseModel):
    """A Monday-anchored week of planned meals."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    week_start: date
    meals: tuple[PlannedMeal, ...] = ()

    @field_validator("week_start")
    @classmethod
    def _must_be_monday(cls, value: date) -> date:
        """Reject any week_start that is not a Monday."""
        if value.weekday() != _MONDAY:
            msg = "week_start must be a Monday"
            raise ValueError(msg)
        return value


class CategoryStatus(BaseModel):
    """Planned servings for one category against its target, with a verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: MedCategory
    planned: float
    target: CategoryTarget
    state: Literal["under", "ok", "over"]


def _state(planned: float, target: CategoryTarget) -> Literal["under", "ok", "over"]:
    """Classify planned servings against a target range."""
    if planned > target.max_servings:
        return "over"
    if planned >= target.min_servings:
        return "ok"
    return "under"


def week_balance(
    plan: WeekPlan,
    recipes: Mapping[str, Recipe],
    targets: Sequence[CategoryTarget],
) -> list[CategoryStatus]:
    """Sum category servings across the week and grade each target.

    Each meal slot counts a recipe's category servings once — portions never
    affect the balance. Multi-category recipes contribute to every category
    they carry. Meals whose recipe code is unknown are skipped (caller logs).
    """
    totals: dict[MedCategory, float] = {}
    for meal in plan.meals:
        recipe = recipes.get(meal.recipe_code)
        if recipe is None:
            continue
        for serving in recipe.mediterranean_categories:
            totals[serving.category] = (
                totals.get(serving.category, 0.0) + serving.servings
            )

    return [
        CategoryStatus(
            category=target.category,
            planned=totals.get(target.category, 0.0),
            target=target,
            state=_state(totals.get(target.category, 0.0), target),
        )
        for target in targets
    ]


def oily_fish_count(plan: WeekPlan, recipes: Mapping[str, Recipe]) -> float:
    """Sum oily-fish servings across the week (each slot counted once)."""
    total = 0.0
    for meal in plan.meals:
        recipe = recipes.get(meal.recipe_code)
        if recipe is None:
            continue
        total += sum(
            serving.servings
            for serving in recipe.mediterranean_categories
            if serving.is_oily_fish
        )
    return total


def _counts_toward(recipe: Recipe, category: MedCategory) -> bool:
    """Return True if recipe contributes positive servings to category."""
    return any(
        serving.category == category and serving.servings > 0
        for serving in recipe.mediterranean_categories
    )


def gap_suggestions(
    statuses: Sequence[CategoryStatus],
    candidates: Sequence[Recipe],
    *,
    planned_codes: frozenset[str] = frozenset(),
    favourite_codes: frozenset[str] = frozenset(),
    limit_per_category: int = 3,
) -> dict[MedCategory, list[Recipe]]:
    """Suggest recipes to fill each under-target category.

    Candidates must count toward the category, be real recipes, not archived,
    and not already in the plan. Ranked by confidence (desc), then favourites,
    then code for a stable order. Favourite and planned codes are supplied by
    the app layer so the domain stays pure.
    """
    suggestions: dict[MedCategory, list[Recipe]] = {}
    for status in statuses:
        if status.state != "under":
            continue
        eligible = [
            recipe
            for recipe in candidates
            if recipe.is_recipe
            and not recipe.archived
            and recipe.code not in planned_codes
            and _counts_toward(recipe, status.category)
        ]
        eligible.sort(
            key=lambda recipe: (
                -recipe.confidence,
                recipe.code not in favourite_codes,
                recipe.code,
            ),
        )
        suggestions[status.category] = eligible[:limit_per_category]
    return suggestions
