import logging
from datetime import date
from functools import cache
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server import MCPServer
from openai import OpenAI
from pydantic import Field, ValidationError

from dispensa.app.plan_week import build_planning_context
from dispensa.app.search_recipes import search_recipes_semantic
from dispensa.deps import build_deps
from dispensa.mcp_server.serializers import (
    to_mcp_detail,
    to_mcp_view,
    to_planning_context,
)
from dispensa.settings import Settings

if TYPE_CHECKING:
    from dispensa.deps import Deps

logger = logging.getLogger(__name__)

# A search returns a shortlist by default and refuses to return the whole
# library: the point of the slim view is to keep the model's context small.
_DEFAULT_SEARCH_LIMIT = 20
_MAX_SEARCH_LIMIT = 100

# FastMCP was renamed MCPServer in the 2.0 SDK; the instance is still the object
# tools hang off and that `mcp.run(...)` starts.
mcp = MCPServer("dispensa")


@cache
def _deps() -> Deps:
    """Wire the repositories once per process, lazily on the first tool call."""
    logger.info("Wiring repositories on first use")
    return build_deps(Settings().database_url)


@cache
def _openai_client() -> OpenAI:
    """Create one OpenAI client per process for query embeddings."""
    return OpenAI(api_key=Settings().require_openai_api_key())


@mcp.tool()
def search_recipes(
    *,
    query: Annotated[
        str,
        Field(
            description=(
                "The user's request in natural language, as intent rather than "
                "keywords — e.g. 'a light vegetarian dinner' or 'dolce per "
                "colazione con proteine'. Full phrases rank better than single words."
            ),
        ),
    ] = "",
    limit: Annotated[
        int,
        Field(
            description=(
                "Maximum number of ranked results to return. Default 20; raise it "
                "(e.g. 30-50) only when the user wants to browse broadly."
            ),
        ),
    ] = _DEFAULT_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Search the Dispensa recipe library by meaning, not keywords.

    Semantic search over each recipe's title, dish, cuisine, proteins, and
    ingredients, so open-ended or descriptive requests work well — e.g.
    'something sweet for breakfast with protein', 'a light fish dinner',
    'qualcosa con la zucca'. Pass the user's request as natural-language intent
    (Italian or English both work); do not reduce it to single keywords, and do
    not retry keyword variants if results look sparse — the ranking already handles
    fuzzy meaning. Returns up to `limit` recipe summaries, ranked best-match first,
    each including `code`, title, dish_type, meal_type, cuisine_type, proteins,
    total_time, score, is_favorite, and post_url. To open one shortlisted result,
    call `get_recipe` with that result's `code`.
    """
    logger.info("search_recipes: query=%r limit=%d", query, limit)
    deps = _deps()
    favourites = set(deps.user_state.all_favorites())
    capped_limit = min(max(limit, 1), _MAX_SEARCH_LIMIT)
    matches = search_recipes_semantic(
        recipes=deps.recipes,
        client=_openai_client(),
        query=query,
        is_recipe=True,
        limit=capped_limit,
    )
    logger.info(
        "search_recipes: %d match(es), returning %d for query=%r",
        len(matches),
        len(matches),
        query,
    )
    return [
        to_mcp_view(recipe, is_favorite=recipe.code in favourites, score=score)
        for recipe, score in matches
    ]


@mcp.tool()
def get_planning_context(
    week_start: Annotated[
        str,
        Field(
            description=(
                "The Monday that starts the target week, as an ISO date "
                "'YYYY-MM-DD'. Must be a Monday."
            ),
        ),
    ],
) -> dict[str, Any]:
    """Return everything needed to plan one week's meals in a single call.

    One payload for the whole planning conversation, so nothing has to be
    re-fetched or re-explained: the meals already slotted for the week (with
    their titles), the Mediterranean-diet `balance` of planned servings against
    each category `target` with an under/ok/over `state`, the `oily_fish`
    tally, `suggestions` of recipes that would fill each under-target category
    (slim views — call `get_recipe` for the full recipe), the weekly `targets`,
    the current `pantry` contents, and the user's `favourite_codes`. Call this
    once at the start of a planning session; after changing a meal, the
    write tool's response already carries the fresh balance.
    """
    logger.info("get_planning_context: week_start=%r", week_start)
    try:
        target = date.fromisoformat(week_start)
    except ValueError as exc:
        msg = "week_start must be an ISO date, e.g. '2024-01-01'"
        raise ValueError(msg) from exc

    deps = _deps()
    try:
        context = build_planning_context(
            week_start=target,
            recipes=deps.recipes,
            plans=deps.plans,
            targets=deps.targets,
            pantry=deps.pantry,
            user_state=deps.user_state,
        )
    except ValidationError as exc:
        msg = f"week_start {week_start!r} is not a Monday"
        raise ValueError(msg) from exc
    return to_planning_context(context)


@mcp.tool()
def get_recipe(
    code: Annotated[
        str,
        Field(
            description=(
                "A recipe's unique code, copied verbatim from a `search_recipes` "
                "result's `code` field (e.g. 'C-KdNbAgsuX')."
            ),
        ),
    ],
) -> dict[str, Any] | None:
    """Return the full stored recipe for its `code`.

    Same summary fields as a search hit, plus ingredients, instructions, times,
    servings, difficulty, tag lists, and mediterranean_categories — everything
    needed to cook from the stored data. The `code` is taken verbatim from a
    `search_recipes` result (e.g. 'C0EUIAZKPkf'). Use this after searching when
    the user wants the actual recipe. Handles one recipe per call.
    """
    logger.info("get_recipe: code=%r", code)
    deps = _deps()
    recipe = deps.recipes.get(code)
    if recipe is None:
        logger.info("get_recipe: %r not found", code)
        return None
    state = deps.user_state.get(code)
    return to_mcp_detail(
        recipe,
        is_favorite=bool(state and state.is_favorite),
        user_notes=state.user_notes if state else None,
    )
