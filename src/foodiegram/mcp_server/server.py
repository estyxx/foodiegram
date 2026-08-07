import logging
from functools import cache
from typing import TYPE_CHECKING, Any

from mcp.server import MCPServer

from foodiegram.deps import build_deps
from foodiegram.mcp_server.serializers import to_mcp_view
from foodiegram.settings import Settings

if TYPE_CHECKING:
    from foodiegram.deps import Deps

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


@mcp.tool()
def search_recipes(
    *,
    query: str = "",
    limit: int = _DEFAULT_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Search the recipe library by text and return slim recipe views.

    query is matched against the title, caption, and ingredients (synonym
    expanded, both languages). Only real recipes are returned, never photo-only
    saves. An empty query lists the library, capped at limit.
    """
    logger.info("search_recipes: query=%r limit=%d", query, limit)
    deps = _deps()
    favourites = set(deps.user_state.all_favorites())
    matches = deps.recipes.find(q=query or None, is_recipe=True)
    capped = matches[: min(max(limit, 1), _MAX_SEARCH_LIMIT)]
    logger.info(
        "search_recipes: %d match(es), returning %d for query=%r",
        len(matches),
        len(capped),
        query,
    )
    return [
        to_mcp_view(recipe, is_favorite=recipe.code in favourites) for recipe in capped
    ]


@mcp.tool()
def get_recipe(code: str) -> dict[str, Any] | None:
    """Return the slim view of one recipe by its code, or None if unknown."""
    logger.info("get_recipe: code=%r", code)
    deps = _deps()
    recipe = deps.recipes.get(code)
    if recipe is None:
        logger.info("get_recipe: %r not found", code)
        return None
    state = deps.user_state.get(code)
    return to_mcp_view(recipe, is_favorite=bool(state and state.is_favorite))
