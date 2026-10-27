import logging
from datetime import date
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field

from dispensa.api_models import RecipeCreate
from dispensa.app.plan_meals import add_draft_meal
from dispensa.app.plan_meals import add_meal as add_meal_use_case
from dispensa.app.plan_meals import clear_meal as clear_meal_use_case
from dispensa.app.plan_meals import set_portions as set_portions_use_case
from dispensa.app.save_custom_recipe import save_custom_recipe
from dispensa.app.update_recipe import RecipeEdit
from dispensa.app.update_recipe import update_recipe as update_recipe_use_case
from dispensa.domain.errors import MealNotFoundError, RecipeNotFoundError
from dispensa.mcp_server.runtime import get_deps, mcp
from dispensa.mcp_server.serializers import to_mcp_detail, to_mcp_plan

if TYPE_CHECKING:
    from dispensa.domain.models import Recipe

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
_DISH_CODE_HINT = (
    "Which dish in the slot, by its recipe `code` (a slot can hold several, "
    "e.g. a main and a side)."
)


def _parse_date(name: str, value: str) -> date:
    """Parse an ISO date argument, naming the argument when it is malformed."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        msg = f"{name} must be an ISO date, e.g. '2024-01-01'; got {value!r}"
        raise ValueError(msg) from exc


def _detail(recipe: Recipe) -> dict[str, Any]:
    """Return the full MCP recipe detail with its current favourite and notes."""
    state = get_deps().user_state.get(recipe.code)
    return to_mcp_detail(
        recipe,
        is_favorite=bool(state and state.is_favorite),
        user_notes=state.user_notes if state else None,
    )


@mcp.tool()
def add_meal(
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
    """Add a dish to one lunch/dinner slot of the week, next to any already there.

    A slot can hold several dishes (a main and a side, a crust and its filling):
    call this once per dish. Nothing is replaced — to swap a dish, clear_meal it
    first. Adding a recipe the slot already holds only updates its portions.
    Pass exactly one of `code` (an existing recipe) or `draft` (a new dish, saved
    to the library as a custom recipe before it is slotted). Returns the fresh
    week: meals with titles, the Mediterranean `balance`, `oily_fish`, and gap
    `suggestions` — no need to call get_planning_context again.
    """
    logger.info("add_meal: %s %s %s code=%r", week_start, day, slot, code)
    target = _parse_date("week_start", week_start)
    meal_day = _parse_date("day", day)
    deps = get_deps()
    try:
        if code is not None and draft is None:
            view = add_meal_use_case(
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
            view = add_draft_meal(
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
    code: Annotated[
        str | None,
        Field(description=f"{_DISH_CODE_HINT} Omit to empty the whole slot."),
    ] = None,
) -> dict[str, Any]:
    """Remove one dish from a lunch/dinner slot, or empty the slot.

    With `code`, only that dish goes; without it, every dish in the slot does.
    Fails if the slot is already empty or lacks that recipe. Returns the fresh
    week (meals, balance, oily_fish, suggestions), like add_meal.
    """
    logger.info("clear_meal: %s %s %s code=%r", week_start, day, slot, code)
    deps = get_deps()
    try:
        view = clear_meal_use_case(
            week_start=_parse_date("week_start", week_start),
            day=_parse_date("day", day),
            meal=slot,
            recipe_code=code,
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
    code: Annotated[
        str | None,
        Field(
            description=f"{_DISH_CODE_HINT} May be omitted when it holds only one.",
        ),
    ] = None,
) -> dict[str, Any]:
    """Change how many portions one dish in a slot makes, keeping its recipe.

    Portions scale the shopping list, never the Mediterranean balance. Fails if
    the slot is empty (use add_meal). Returns the fresh week, like add_meal.
    """
    logger.info(
        "set_portions: %s %s %s code=%r portions=%d",
        week_start,
        day,
        slot,
        code,
        portions,
    )
    deps = get_deps()
    try:
        view = set_portions_use_case(
            week_start=_parse_date("week_start", week_start),
            day=_parse_date("day", day),
            meal=slot,
            recipe_code=code,
            portions=portions,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            user_state=deps.user_state,
        )
    except (MealNotFoundError, RecipeNotFoundError) as exc:
        raise ValueError(str(exc)) from exc
    return to_mcp_plan(view)


@mcp.tool()
def save_recipe(
    *,
    draft: Annotated[
        RecipeCreate,
        Field(
            description=(
                "The custom recipe: title, ingredients and instructions verbatim "
                "(any language), mediterranean_categories set by hand, and "
                "inspired_by listing the codes of the posts it is a version of."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Save a custom recipe (your own version of a dish) to the library.

    `inspired_by` may name any saved post, including ones that are not full
    recipes. Returns the stored recipe with its new `code` (starting 'm-'),
    which add_meal accepts.
    """
    logger.info("save_recipe: title=%r", draft.title)
    recipe = save_custom_recipe(draft.model_dump(), recipes=get_deps().recipes)
    return _detail(recipe)


@mcp.tool()
def update_recipe(
    *,
    code: Annotated[str, Field(description=f"The recipe to edit. {_CODE_HINT}")],
    is_favorite: Annotated[
        bool | None,
        Field(description="Mark or unmark as a favourite. Omit to leave unchanged."),
    ] = None,
    user_notes: Annotated[
        str | None,
        Field(description="Replace the notes; '' clears them. Omit to leave unchanged."),
    ] = None,
    base_servings: Annotated[
        int | None,
        Field(
            description=(
                "How many servings the recipe makes as written. A hand edit: later "
                "re-extractions never overwrite it. Omit to leave unchanged."
            ),
        ),
    ] = None,
) -> dict[str, Any]:
    """Edit a recipe's favourite flag, notes, or base servings.

    Only the arguments you pass change. Returns the full updated recipe.
    """
    logger.info("update_recipe: code=%r", code)
    provided = {
        "is_favorite": is_favorite,
        "user_notes": user_notes,
        "base_servings": base_servings,
    }
    edit = RecipeEdit.model_validate(
        {field: value for field, value in provided.items() if value is not None},
    )
    deps = get_deps()
    try:
        recipe = update_recipe_use_case(
            code,
            edit=edit,
            recipes=deps.recipes,
            user_state=deps.user_state,
        )
    except RecipeNotFoundError as exc:
        msg = f"{exc}. {_CODE_HINT}"
        raise ValueError(msg) from exc
    return _detail(recipe)
