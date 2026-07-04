from foodiegram.app.review_categories import (
    apply_reviewed_categories,
    needs_category_review,
    select_for_review,
)
from foodiegram.domain.enums import MedCategory
from foodiegram.domain.models import (
    CategoryServing,
    ExtractedCategoryServing,
    Recipe,
)

_KEYWORDS = frozenset({"guanciale", "pancetta", "salame"})

_BASE = Recipe(
    code="ABC",
    pk="1",
    post_url="https://instagram.com/p/ABC/",
    caption="a caption",
    title="Test recipe",
    ingredients=[],
    instructions=[],
    confidence=1.0,
)


def test_low_confidence_needs_review() -> None:
    """A recipe below the confidence threshold is selected."""
    recipe = _BASE.model_copy(update={"confidence": 0.5})

    assert needs_category_review(recipe, processed_meat_keywords=_KEYWORDS) is True


def test_empty_categories_with_proteins_needs_review() -> None:
    """A protein-bearing recipe with no categories is selected."""
    recipe = _BASE.model_copy(update={"proteins": ["chicken"]})

    assert needs_category_review(recipe, processed_meat_keywords=_KEYWORDS) is True


def test_processed_meat_keyword_without_category_needs_review() -> None:
    """A cured-meat ingredient without a processed_meat category is selected."""
    recipe = _BASE.model_copy(
        update={
            "ingredients": ["200g guanciale a cubetti"],
            "mediterranean_categories": [CategoryServing(category=MedCategory.EGGS)],
        },
    )

    assert needs_category_review(recipe, processed_meat_keywords=_KEYWORDS) is True


def test_clean_recipe_not_selected() -> None:
    """A confident, categorised recipe with no cured meat is not selected."""
    recipe = _BASE.model_copy(
        update={
            "proteins": ["chicken"],
            "ingredients": ["chicken breast"],
            "mediterranean_categories": [
                CategoryServing(category=MedCategory.POULTRY),
            ],
        },
    )

    assert needs_category_review(recipe, processed_meat_keywords=_KEYWORDS) is False


def test_existing_processed_meat_category_not_selected() -> None:
    """A cured-meat recipe already tagged processed_meat is not selected."""
    recipe = _BASE.model_copy(
        update={
            "ingredients": ["guanciale"],
            "mediterranean_categories": [
                CategoryServing(category=MedCategory.PROCESSED_MEAT),
            ],
        },
    )

    assert needs_category_review(recipe, processed_meat_keywords=_KEYWORDS) is False


def test_select_for_review_applies_limit() -> None:
    """select_for_review caps the result at the requested limit."""
    recipes = [
        _BASE.model_copy(update={"code": f"C{i}", "confidence": 0.1}) for i in range(3)
    ]
    limit = 2

    selected = select_for_review(
        recipes,
        processed_meat_keywords=_KEYWORDS,
        limit=limit,
    )

    assert len(selected) == limit


def test_accept_path_marks_manual_and_edited() -> None:
    """Accepting proposals writes source=manual and marks the recipe edited."""
    proposed = [
        ExtractedCategoryServing(category="eggs"),
        ExtractedCategoryServing(category="processed_meat"),
    ]

    updated = apply_reviewed_categories(_BASE, proposed)

    assert updated.edited_by_user is True
    assert [c.category for c in updated.mediterranean_categories] == [
        MedCategory.EGGS,
        MedCategory.PROCESSED_MEAT,
    ]
    assert all(c.source == "manual" for c in updated.mediterranean_categories)


def test_accept_path_drops_unknown_category() -> None:
    """An unknown proposed category is dropped from the accepted set."""
    proposed = [
        ExtractedCategoryServing(category="eggs"),
        ExtractedCategoryServing(category="bogus"),
    ]

    updated = apply_reviewed_categories(_BASE, proposed)

    assert [c.category for c in updated.mediterranean_categories] == [MedCategory.EGGS]
