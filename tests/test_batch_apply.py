from datetime import UTC, datetime

from foodiegram.ai.batch import PROMPT_VERSION, apply_extracted
from foodiegram.domain.enums import Course, MedCategory
from foodiegram.domain.models import (
    ExtractedCategoryServing,
    ExtractedRecipe,
    Recipe,
)

_EXTRACTED_AT = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
# A snapshot distinct from the module constant, proving the stamp comes from the
# response's `model` field rather than the MODEL constant.
_MODEL_SNAPSHOT = "gpt-5.4-mini-2026-03-17"


def _existing() -> Recipe:
    """Build a recipe carrying user-owned edits a re-extraction must keep."""
    return Recipe(
        code="ABC",
        pk="1",
        post_url="https://instagram.com/p/ABC/",
        caption="Original caption long enough to be a real recipe post about food.",
        title="Old Title",
        ingredients=["old ingredient"],
        instructions=["old step"],
        edited_by_user=True,
        edited_fields=frozenset({"ingredients"}),
        thumbnail_url="https://cdn/thumb.jpg",
        cloudinary_url="https://cdn/cloud.jpg",
    )


def _fresh_extraction() -> ExtractedRecipe:
    """Build a new extraction whose classification fields differ from existing."""
    return ExtractedRecipe(
        title="New Title",
        ingredients=["new ingredient"],
        instructions=["new step"],
        dish_type="pasta",
        meal_type="lunch",
        cuisine_type="italian",
        difficulty="easy",
        course="primo",
        mediterranean_categories=[
            ExtractedCategoryServing(category="eggs"),
            ExtractedCategoryServing(category="processed_meat"),
        ],
        proteins=["eggs"],
        vegetables=[],
        grains_starches=["pasta"],
        herbs_spices=[],
        cooking_methods=["boiling"],
        equipment=["pot"],
        prep_time="10 minutes",
        cook_time="15 minutes",
        total_time="25 minutes",
        servings="2",
        temperature="hot",
        texture=["creamy"],
        flavor_profile=["savory"],
        dietary_tags=[],
        health_tags=[],
        season=["year_round"],
        occasion=["weeknight"],
        skill_level="beginner",
        style_tags=["home_cooking"],
        prep_style=["quick"],
        is_recipe=True,
        confidence=0.9,
    )


def test_apply_preserves_user_owned_fields() -> None:
    """User-owned fields survive an extraction while classification fields update."""
    existing = _existing()

    result = apply_extracted(
        existing,
        _fresh_extraction(),
        extracted_at=_EXTRACTED_AT,
        model_used=_MODEL_SNAPSHOT,
    )
    recipe = result.recipe

    assert recipe.edited_by_user is True
    assert recipe.edited_fields == frozenset({"ingredients"})
    assert recipe.thumbnail_url == "https://cdn/thumb.jpg"
    assert recipe.cloudinary_url == "https://cdn/cloud.jpg"


def test_apply_updates_extracted_fields() -> None:
    """Extracted content and classification fields replace the old values."""
    result = apply_extracted(
        _existing(),
        _fresh_extraction(),
        extracted_at=_EXTRACTED_AT,
        model_used=_MODEL_SNAPSHOT,
    )
    recipe = result.recipe

    assert recipe.title == "New Title"
    assert recipe.ingredients == ["new ingredient"]
    assert recipe.instructions == ["new step"]
    assert recipe.course is Course.PRIMO
    assert [c.category for c in recipe.mediterranean_categories] == [
        MedCategory.EGGS,
        MedCategory.PROCESSED_MEAT,
    ]


def test_apply_stamps_provenance() -> None:
    """The merge stamps prompt_version, model_used, and extracted_at."""
    result = apply_extracted(
        _existing(),
        _fresh_extraction(),
        extracted_at=_EXTRACTED_AT,
        model_used=_MODEL_SNAPSHOT,
    )
    recipe = result.recipe

    assert recipe.prompt_version == PROMPT_VERSION
    assert recipe.model_used == _MODEL_SNAPSHOT
    assert recipe.extracted_at == _EXTRACTED_AT
