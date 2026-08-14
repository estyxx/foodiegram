from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from foodiegram.domain.models import Recipe


def to_mcp_view(
    recipe: Recipe,
    *,
    is_favorite: bool = False,
    score: float | None = None,
) -> dict[str, Any]:
    """Return the slim search-index view of a recipe for the MCP wire.

    The same shape the browser search index carries (RecipeSummary's core), not
    the full thirty-field recipe: a model planning a week needs the facets and a
    link back to the post, and every extra field is context it must pay to read.
    """
    view: dict[str, Any] = {
        "code": recipe.code,
        "title": recipe.title,
        "dish_type": recipe.dish_type.value,
        "meal_type": recipe.meal_type.value,
        "cuisine_type": recipe.cuisine_type.value,
        "proteins": recipe.proteins,
        "total_time": recipe.total_time,
        "is_favorite": is_favorite,
        "post_url": recipe.post_url,
    }
    if score is not None:
        view["score"] = score
    return view
