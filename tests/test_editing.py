from datetime import UTC, datetime

from foodiegram.domain.editing import PROTECTED_FIELDS, promote
from foodiegram.domain.enums import Course, MedCategory, RecipeSource
from foodiegram.domain.models import (
    ExtractedCategoryServing,
    ExtractedRecipe,
    Extraction,
    Recipe,
)

_EXTRACTED_AT = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _extracted() -> ExtractedRecipe:
    """Build an extraction payload whose values differ from the current recipe."""
    return ExtractedRecipe(
        title="New Title",
        ingredients=["new ingredient"],
        instructions=["new step"],
        summary="A new one-sentence summary.",
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
        dietary_tags=["vegetarian"],
        health_tags=[],
        season=["year_round"],
        occasion=["weeknight"],
        skill_level="beginner",
        style_tags=["home_cooking"],
        prep_style=["quick"],
        is_recipe=True,
        confidence=0.9,
    )


def _extraction() -> Extraction:
    """Wrap the payload in an immutable Extraction run."""
    return Extraction(
        id=1,
        recipe_code="ABC",
        prompt_version="2",
        model="gpt-5.4-mini-2026-03-17",
        batch_id="batch_abc",
        kind="batch",
        extracted_at=_EXTRACTED_AT,
        payload=_extracted(),
    )


def _current() -> Recipe:
    """Build a recipe carrying a user edit and protected media/identity values."""
    return Recipe(
        code="ABC",
        source=RecipeSource.MANUAL,
        pk="99",
        post_url="https://instagram.com/p/ABC/",
        caption="User-kept caption",
        title="Old Title",
        ingredients=["user ingredient"],
        instructions=["old step"],
        course=Course.UNKNOWN,
        cloudinary_url="https://cdn/cloud.jpg",
        thumbnail_url="https://cdn/thumb.jpg",
        archived=True,
        edited_fields=frozenset({"ingredients"}),
        prompt_version="1",
        model_used="old-model",
    )


def test_promote_keeps_edited_updates_rest_and_is_idempotent() -> None:
    """THE ANCHOR: edited ingredients stay, everything else updates, idempotently."""
    current = _current()
    extraction = _extraction()

    promoted = promote(current, extraction)

    # The user's edited field is preserved verbatim.
    assert promoted.ingredients == ["user ingredient"]

    # Every other extracted field takes the extraction's value.
    assert promoted.title == "New Title"
    assert promoted.instructions == ["new step"]
    assert promoted.summary == "A new one-sentence summary."
    assert promoted.course is Course.PRIMO
    assert [c.category for c in promoted.mediterranean_categories] == [
        MedCategory.EGGS,
        MedCategory.PROCESSED_MEAT,
    ]
    assert promoted.dietary_tags == ["vegetarian"]

    # Provenance is stamped from the extraction.
    assert promoted.prompt_version == "2"
    assert promoted.model_used == "gpt-5.4-mini-2026-03-17"
    assert promoted.extracted_at == _EXTRACTED_AT

    # Promoting the same extraction again changes nothing.
    assert promote(promoted, extraction) == promoted


def test_promote_never_touches_protected_fields() -> None:
    """Protected identity and media fields survive even when the extraction differs."""
    current = _current()

    promoted = promote(current, _extraction())

    for field in PROTECTED_FIELDS:
        assert getattr(promoted, field) == getattr(current, field), field

    # Spot-check the values the extraction would otherwise have overwritten.
    assert promoted.source is RecipeSource.MANUAL
    assert promoted.pk == "99"
    assert promoted.caption == "User-kept caption"
    assert promoted.cloudinary_url == "https://cdn/cloud.jpg"
    assert promoted.thumbnail_url == "https://cdn/thumb.jpg"
    assert promoted.archived is True
    assert promoted.edited_fields == frozenset({"ingredients"})
