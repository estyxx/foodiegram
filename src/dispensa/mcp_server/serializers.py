from typing import TYPE_CHECKING, Any

from dispensa.api_models import RecipeDetail

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dispensa.app.plan_week import PlanningContext, WeekPlanView
    from dispensa.domain.models import Recipe
    from dispensa.domain.pantry import PantryItem


def to_mcp_view(
    recipe: Recipe,
    *,
    is_favorite: bool = False,
    score: float | None = None,
) -> dict[str, Any]:
    """Return the slim search-index view of a recipe for the MCP wire.

    The browser search index's core plus the balance inputs (categories and
    servings) and difficulty, not the full thirty-field recipe: a model planning
    a week needs these without a get_recipe call per hit, and every extra field
    is context it must pay to read.
    """
    view: dict[str, Any] = {
        "code": recipe.code,
        "title": recipe.title,
        "dish_type": recipe.dish_type.value,
        "meal_type": recipe.meal_type.value,
        "cuisine_type": recipe.cuisine_type.value,
        "difficulty": recipe.difficulty.value,
        "mediterranean_categories": [
            {
                "category": serving.category.value,
                "servings": serving.servings,
                "is_oily_fish": serving.is_oily_fish,
            }
            for serving in recipe.mediterranean_categories
        ],
        "proteins": recipe.proteins,
        "total_time": recipe.total_time,
        "is_favorite": is_favorite,
        "post_url": recipe.post_url,
    }
    if score is not None:
        view["score"] = score
    return view


def to_mcp_plan(view: WeekPlanView) -> dict[str, Any]:
    """Serialise one week's meals, balance, oily fish and gaps for the MCP wire.

    The MCP twin of the API's PlanResponse: what every plan write tool returns,
    so a planning conversation never needs a follow-up read. Meals carry their
    recipe titles so the model can talk about them without a get_recipe call.
    """
    return {
        "week_start": view.plan.week_start.isoformat(),
        "meals": [meal.model_dump(mode="json") for meal in view.meals],
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
    }


def to_mcp_pantry(items: Sequence[PantryItem]) -> list[dict[str, Any]]:
    """Serialise pantry items for the MCP wire; `id` is what removal takes."""
    return [
        {
            "id": item.id,
            "name": item.name,
            "kind": item.kind,
            "location": item.location.value,
            "quantity": item.quantity,
            "expires": item.expires.isoformat() if item.expires else None,
        }
        for item in items
    ]


def to_planning_context(context: PlanningContext) -> dict[str, Any]:
    """Serialise the week's planning payload for the MCP wire.

    The week as to_mcp_plan shapes it, plus the small reference lists (targets,
    pantry, favourites) a planner reads once per session.
    """
    return {
        **to_mcp_plan(context.week),
        "targets": [
            {
                "category": target.category.value,
                "min_servings": target.min_servings,
                "max_servings": target.max_servings,
            }
            for target in context.targets
        ],
        "pantry": to_mcp_pantry(context.pantry),
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
