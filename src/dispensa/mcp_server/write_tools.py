import logging
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import Field

from dispensa.api_models import RecipeCreate
from dispensa.app.plan_meals import clear_meal as clear_meal_use_case
from dispensa.app.plan_meals import set_draft_meal
from dispensa.app.plan_meals import set_meal as set_meal_use_case
from dispensa.app.plan_meals import set_portions as set_portions_use_case
from dispensa.domain.errors import MealNotFoundError, RecipeNotFoundError
from dispensa.mcp_server.runtime import get_deps, mcp
from dispensa.mcp_server.serializers import to_mcp_plan

logger = logging.getLogger(__name__)

_WEEK_START = Field(
    description="The Monday that starts the target week, as an ISO date 'YYYY-MM-DD'.",
)
_DAY = Field(
    description=(
        "The day of the meal, as an ISO date 'YYYY-MM-DD' within the week "
        "(Monday..Sunday of week_start)."
    ),
)
_SLOT = Field(description="Which meal of the day: 'lunch' or 'dinner'.")
_CODE_HINT = "Copy a `code` from search_recipes or get_planning_context."


def _parse_date(name: str, value: str) -> date:
    """Parse an ISO date argument, naming the argument when it is malformed."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        msg = f"{name} must be an ISO date, e.g. '2024-01-01'; got {value!r}"
        raise ValueError(msg) from exc


@mcp.tool()
def set_meal(
    *,
    week_start: Annotated[str, _WEEK_START],
    day: Annotated[str, _DAY],
    slot: Annotated[Literal["lunch", "dinner"], _SLOT],
    code: Annotated[
        str | None,
        Field(description=f"The recipe to slot. {_CODE_HINT} Omit when passing draft."),
    ] = None,
    draft: Annotated[
        RecipeCreate | None,
        Field(
            description=(
                "A dish not in the library yet: title, ingredients, instructions "
                "(may be []), and mediterranean_categories set by hand. It is saved "
                "as a custom recipe first, then slotted. Omit when passing code."
            ),
        ),
    ] = None,
    portions: Annotated[
        int,
        Field(description="How many portions to cook; scales the shopping list only."),
    ] = 2,
) -> dict[str, Any]:
    """Put a meal in one lunch/dinner slot of the week, replacing what was there.

    Pass exactly one of `code` (an existing recipe) or `draft` (a new dish, saved
    to the library as a custom recipe before it is slotted). Returns the fresh
    week: meals with titles, the Mediterranean `balance`, `oily_fish`, and gap
    `suggestions` — no need to call get_planning_context again.
    """
    logger.info("set_meal: %s %s %s code=%r", week_start, day, slot, code)
    target = _parse_date("week_start", week_start)
    meal_day = _parse_date("day", day)
    deps = get_deps()
    try:
        if code is not None and draft is None:
            view = set_meal_use_case(
                week_start=target,
                day=meal_day,
                meal=slot,
                recipe_code=code,
                portions=portions,
                recipes=deps.recipes,
                plans=deps.plans,
                targets=deps.targets,
                user_state=deps.user_state,
            )
        elif draft is not None and code is None:
            view = set_draft_meal(
                draft.model_dump(),
                week_start=target,
                day=meal_day,
                meal=slot,
                portions=portions,
                recipes=deps.recipes,
                plans=deps.plans,
                targets=deps.targets,
                user_state=deps.user_state,
            )
        else:
            msg = "Pass exactly one of code (an existing recipe) or draft (a new dish)"
            raise ValueError(msg)
    except RecipeNotFoundError as exc:
        msg = f"{exc}. {_CODE_HINT}"
        raise ValueError(msg) from exc
    return to_mcp_plan(view)


@mcp.tool()
def clear_meal(
    *,
    week_start: Annotated[str, _WEEK_START],
    day: Annotated[str, _DAY],
    slot: Annotated[Literal["lunch", "dinner"], _SLOT],
) -> dict[str, Any]:
    """Empty one lunch/dinner slot of the week.

    Fails if the slot is already empty. Returns the fresh week (meals, balance,
    oily_fish, suggestions), like set_meal.
    """
    logger.info("clear_meal: %s %s %s", week_start, day, slot)
    deps = get_deps()
    try:
        view = clear_meal_use_case(
            week_start=_parse_date("week_start", week_start),
            day=_parse_date("day", day),
            meal=slot,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        )
    except MealNotFoundError as exc:
        raise ValueError(str(exc)) from exc
    return to_mcp_plan(view)


@mcp.tool()
def set_portions(
    *,
    week_start: Annotated[str, _WEEK_START],
    day: Annotated[str, _DAY],
    slot: Annotated[Literal["lunch", "dinner"], _SLOT],
    portions: Annotated[int, Field(description="The new portion count, at least 1.")],
) -> dict[str, Any]:
    """Change how many portions the meal already in a slot makes, keeping its recipe.

    Portions scale the shopping list, never the Mediterranean balance. Fails if
    the slot is empty (use set_meal). Returns the fresh week, like set_meal.
    """
    logger.info("set_portions: %s %s %s portions=%d", week_start, day, slot, portions)
    deps = get_deps()
    try:
        view = set_portions_use_case(
            week_start=_parse_date("week_start", week_start),
            day=_parse_date("day", day),
            meal=slot,
            portions=portions,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        )
    except (MealNotFoundError, RecipeNotFoundError) as exc:
        raise ValueError(str(exc)) from exc
    return to_mcp_plan(view)
