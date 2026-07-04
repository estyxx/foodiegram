from typing import TYPE_CHECKING

from foodiegram.domain.enums import MedCategory
from foodiegram.domain.models import CategoryServing, ExtractedCategoryServing, Recipe

if TYPE_CHECKING:
    from collections.abc import Sequence

CONFIDENCE_THRESHOLD = 0.6
_MED_CATEGORY_VALUES = frozenset(category.value for category in MedCategory)


def _mentions_processed_meat(
    ingredients: Sequence[str],
    keywords: frozenset[str],
) -> bool:
    """Return True if any processed-meat keyword appears in the ingredient lines."""
    text = " ".join(ingredients).lower()
    return any(keyword in text for keyword in keywords)


def needs_category_review(
    recipe: Recipe,
    *,
    processed_meat_keywords: frozenset[str],
    confidence_threshold: float = CONFIDENCE_THRESHOLD,
) -> bool:
    """Return True if a recipe should go through interactive category review."""
    if recipe.confidence < confidence_threshold:
        return True
    if not recipe.mediterranean_categories and recipe.proteins:
        return True
    has_processed = any(
        serving.category is MedCategory.PROCESSED_MEAT
        for serving in recipe.mediterranean_categories
    )
    return not has_processed and _mentions_processed_meat(
        recipe.ingredients,
        processed_meat_keywords,
    )


def select_for_review(
    recipes: Sequence[Recipe],
    *,
    processed_meat_keywords: frozenset[str],
    limit: int | None = None,
) -> list[Recipe]:
    """Return recipes needing category review, capped at limit when given."""
    selected = [
        recipe
        for recipe in recipes
        if needs_category_review(
            recipe,
            processed_meat_keywords=processed_meat_keywords,
        )
    ]
    if limit is not None:
        return selected[:limit]
    return selected


def apply_reviewed_categories(
    recipe: Recipe,
    proposed: Sequence[ExtractedCategoryServing],
) -> Recipe:
    """Return a recipe with reviewer-approved categories (source=manual, edited)."""
    categories = [
        CategoryServing(
            category=MedCategory(serving.category),
            servings=serving.servings,
            is_oily_fish=serving.is_oily_fish,
            source="manual",
        )
        for serving in proposed
        if serving.category in _MED_CATEGORY_VALUES
    ]
    return recipe.model_copy(
        update={"mediterranean_categories": categories, "edited_by_user": True},
    )
