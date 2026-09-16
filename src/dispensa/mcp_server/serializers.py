from typing import TYPE_CHECKING, Any

from dispensa.api_models import RecipeDetail

if TYPE_CHECKING:
    from dispensa.app.plan_week import PlanningContext
    from dispensa.domain.models import Recipe


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


def to_planning_context(context: PlanningContext) -> dict[str, Any]:
    """Serialise the week's planning payload for the MCP wire.

    Slim recipe views for gap suggestions (the model pays to read every field);
    everything else is small scalars it needs to reason about balance.
    """
    view = context.week
    return {
        "week_start": view.plan.week_start.isoformat(),
        "meals": [meal.model_dump(mode="json") for meal in context.meals],
        "balance": [
            {
                "category": status.category.value,
                "planned": status.planned,
                "min_servings": status.target.min_servings,
                "max_servings": status.target.max_servings,
                "state": status.state,
            }
            for status in view.balance
        ],
        "oily_fish": view.oily_fish,
        "suggestions": [
            {
                "category": category.value,
                "recipes": [to_mcp_view(recipe) for recipe in recipes_for],
            }
            for category, recipes_for in view.suggestions.items()
        ],
        "targets": [
            {
                "category": target.category.value,
                "min_servings": target.min_servings,
                "max_servings": target.max_servings,
            }
            for target in context.targets
        ],
        "pantry": [
            {
                "name": item.name,
                "kind": item.kind,
                "expires": item.expires.isoformat() if item.expires else None,
            }
            for item in context.pantry
        ],
        "favourite_codes": list(context.favourite_codes),
    }


def to_mcp_detail(
    recipe: Recipe,
    *,
    is_favorite: bool = False,
    user_notes: str | None = None,
) -> dict[str, Any]:
    """Return the full recipe detail for MCP get_recipe, reusing RecipeDetail."""
    detail = RecipeDetail.model_validate(
        {
            **recipe.model_dump(),
            "is_favorite": is_favorite,
            "user_notes": user_notes,
        },
    )
    return detail.model_dump(mode="json")
