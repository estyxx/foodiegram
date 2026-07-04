from datetime import UTC, datetime

from foodiegram.domain.diffing import diff_against_recipe, diff_payloads
from foodiegram.domain.models import (
    ExtractedCategoryServing,
    ExtractedRecipe,
    Extraction,
    Recipe,
)

_EXTRACTED_AT = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _extracted() -> ExtractedRecipe:
    """Build a minimal valid extraction payload for diffing tests."""
    return ExtractedRecipe(
        title="Carbonara",
        ingredients=["guanciale", "uova"],
        instructions=["fry", "toss"],
        dish_type="pasta",
        meal_type="lunch",
        cuisine_type="italian",
        difficulty="easy",
        course="primo",
        mediterranean_categories=[ExtractedCategoryServing(category="eggs")],
        proteins=["uova"],
        vegetables=[],
        grains_starches=["pasta"],
        herbs_spices=[],
        cooking_methods=["boil"],
        equipment=["pot"],
        prep_time="10m",
        cook_time="15m",
        total_time="25m",
        servings="2",
        temperature="hot",
        texture=["creamy"],
        flavor_profile=["savory"],
        dietary_tags=["quick", "comfort"],
        health_tags=[],
        season=[],
        occasion=[],
        skill_level="home",
        style_tags=[],
        prep_style=[],
        is_recipe=True,
        confidence=0.9,
    )


def test_reordered_dietary_tags_yield_no_diff() -> None:
    """Tag lists compare order-insensitively: a reorder is not a change."""
    a = _extracted()
    b = a.model_copy(update={"dietary_tags": ["comfort", "quick"]})

    assert diff_payloads(a, b) == []


def test_reordered_instructions_yield_a_diff() -> None:
    """Instructions compare order-sensitively: a reorder is a real change."""
    a = _extracted()
    b = a.model_copy(update={"instructions": ["toss", "fry"]})

    diffs = diff_payloads(a, b)

    assert [d.field for d in diffs] == ["instructions"]
    assert diffs[0].old == ["fry", "toss"]
    assert diffs[0].new == ["toss", "fry"]


def test_changed_categories_diff_shows_old_and_new() -> None:
    """A changed category list surfaces as a diff with old and new visible."""
    a = _extracted()
    new_categories = [ExtractedCategoryServing(category="dairy")]
    b = a.model_copy(update={"mediterranean_categories": new_categories})

    diffs = diff_payloads(a, b)

    assert [d.field for d in diffs] == ["mediterranean_categories"]
    assert diffs[0].old == [ExtractedCategoryServing(category="eggs")]
    assert diffs[0].new == new_categories


def _extraction(payload: ExtractedRecipe) -> Extraction:
    """Wrap a payload in an Extraction run."""
    return Extraction(
        id=1,
        recipe_code="ABC",
        prompt_version="2",
        model="gpt-5.4-mini-2026-03-17",
        batch_id=None,
        kind="repair",
        extracted_at=_EXTRACTED_AT,
        payload=payload,
    )


def test_diff_against_recipe_hides_edited_fields() -> None:
    """The dry-run view omits fields the user has edited, but keeps the rest."""
    recipe = Recipe(
        code="ABC",
        pk="1",
        post_url="https://instagram.com/p/ABC/",
        caption="cap",
        title="User Title",
        ingredients=["guanciale", "uova"],
        instructions=["old"],
        edited_fields=frozenset({"title"}),
    )
    extraction = _extraction(_extracted())

    fields = {d.field for d in diff_against_recipe(recipe, extraction)}

    assert "title" not in fields
    assert "instructions" in fields
