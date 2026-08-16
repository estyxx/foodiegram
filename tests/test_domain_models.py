import pytest

from foodiegram.domain.enums import Course, MedCategory, RecipeSource
from foodiegram.domain.models import (
    CategoryServing,
    ExtractedCategoryServing,
    ExtractedRecipe,
    Recipe,
)

_SECONDARY_SERVINGS = 0.5


def _extracted(
    *,
    course: str = "primo",
    mediterranean_categories: list[ExtractedCategoryServing] | None = None,
) -> ExtractedRecipe:
    """Build a minimal valid ExtractedRecipe for mapping tests."""
    return ExtractedRecipe(
        title="Carbonara",
        ingredients=["guanciale", "uova", "pecorino"],
        instructions=["cook"],
        dish_type="pasta",
        meal_type="lunch",
        cuisine_type="italian",
        difficulty="easy",
        course=course,
        mediterranean_categories=mediterranean_categories or [],
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
        dietary_tags=[],
        health_tags=[],
        season=[],
        occasion=[],
        skill_level="home",
        style_tags=[],
        prep_style=[],
        is_recipe=True,
        confidence=0.9,
    )


def test_maps_multiple_valid_categories() -> None:
    """A recipe can count toward multiple categories, all mapped in order."""
    extracted = _extracted(
        mediterranean_categories=[
            ExtractedCategoryServing(category="eggs"),
            ExtractedCategoryServing(category="processed_meat"),
            ExtractedCategoryServing(category="dairy", servings=_SECONDARY_SERVINGS),
        ],
    )

    mapped = Recipe.from_extracted(
        code="ABC",
        pk="1",
        caption=None,
        extracted=extracted,
    )

    assert mapped.dropped_categories == ()
    assert [c.category for c in mapped.recipe.mediterranean_categories] == [
        MedCategory.EGGS,
        MedCategory.PROCESSED_MEAT,
        MedCategory.DAIRY,
    ]
    assert mapped.recipe.mediterranean_categories[2].servings == _SECONDARY_SERVINGS
    assert all(c.source == "llm" for c in mapped.recipe.mediterranean_categories)


def test_unknown_category_dropped_siblings_survive() -> None:
    """An unknown category string is dropped; valid siblings are kept."""
    extracted = _extracted(
        mediterranean_categories=[
            ExtractedCategoryServing(category="fish", is_oily_fish=True),
            ExtractedCategoryServing(category="shellfish"),
            ExtractedCategoryServing(category="legumes"),
        ],
    )

    mapped = Recipe.from_extracted(
        code="ABC",
        pk="1",
        caption=None,
        extracted=extracted,
    )

    assert mapped.dropped_categories == ("shellfish",)
    assert [c.category for c in mapped.recipe.mediterranean_categories] == [
        MedCategory.FISH,
        MedCategory.LEGUMES,
    ]
    assert mapped.recipe.mediterranean_categories[0].is_oily_fish is True


def test_unknown_course_falls_back_to_unknown() -> None:
    """An unrecognised course string maps to Course.UNKNOWN."""
    extracted = _extracted(course="brunch")

    mapped = Recipe.from_extracted(
        code="ABC",
        pk="1",
        caption=None,
        extracted=extracted,
    )

    assert mapped.recipe.course is Course.UNKNOWN


def test_known_course_maps() -> None:
    """A valid course string maps to the matching Course member."""
    extracted = _extracted(course="secondo")

    mapped = Recipe.from_extracted(
        code="ABC",
        pk="1",
        caption=None,
        extracted=extracted,
    )

    assert mapped.recipe.course is Course.SECONDO


def test_extracted_category_serving_defaults() -> None:
    """Servings and is_oily_fish default sensibly on the extracted sub-model."""
    serving = ExtractedCategoryServing(category="fish")

    assert serving.servings == 1.0
    assert serving.is_oily_fish is False


def test_category_serving_defaults() -> None:
    """servings, is_oily_fish and source default sensibly on the domain model."""
    serving = CategoryServing(category=MedCategory.FISH)

    assert serving.servings == 1.0
    assert serving.is_oily_fish is False
    assert serving.source == "llm"


def test_legacy_recipe_json_without_new_fields_validates() -> None:
    """A pre-v2 recipe JSON without the new fields validates via defaults."""
    legacy = {
        "code": "ABC",
        "pk": "1",
        "post_url": "https://instagram.com/p/ABC/",
        "caption": None,
        "title": "Old recipe",
        "ingredients": ["water"],
        "instructions": ["boil"],
    }

    recipe = Recipe.model_validate(legacy)

    assert recipe.course is Course.UNKNOWN
    assert recipe.mediterranean_categories == []
    assert recipe.prompt_version is None


def test_manual_recipe_without_instagram_fields_validates() -> None:
    """A manual recipe with pk/post_url/caption all None validates."""
    recipe = Recipe(
        code="m-torta-abcd",
        source=RecipeSource.MANUAL,
        pk=None,
        post_url=None,
        caption=None,
        title="Torta della nonna",
        ingredients=["farina", "uova"],
        instructions=["mescola", "inforna"],
    )

    assert recipe.source is RecipeSource.MANUAL
    assert recipe.pk is None
    assert recipe.post_url is None
    assert recipe.caption is None
    assert recipe.edited_fields == frozenset()
    assert recipe.archived is False


@pytest.mark.parametrize("stored", ["None", "none", "unknown", "Unknown", "", "  "])
def test_stringified_absence_becomes_a_real_missing_title(stored: str) -> None:
    """A title that only spells absence is normalised to None, not kept as text."""
    recipe = Recipe(
        code="ABC",
        pk="1",
        post_url=None,
        caption=None,
        title=stored,
        ingredients=[],
        instructions=[],
    )

    assert recipe.title is None


def test_a_real_title_survives_normalisation() -> None:
    """Only the absence words are touched; a genuine title is left alone."""
    recipe = Recipe(
        code="ABC",
        pk="1",
        post_url=None,
        caption=None,
        title="Nonna's unknown pasta",
        ingredients=[],
        instructions=[],
    )

    assert recipe.title == "Nonna's unknown pasta"


def test_extraction_that_gave_up_on_the_title_yields_none() -> None:
    """The LLM saying "unknown" is an absence too, not a name."""
    mapped = Recipe.from_extracted(
        code="ABC",
        pk="1",
        caption=None,
        extracted=_extracted().model_copy(update={"title": "unknown"}),
    )

    assert mapped.recipe.title is None


@pytest.mark.parametrize(
    ("ingredients", "instructions", "expected"),
    [
        (["farina"], ["mescola"], True),
        (["farina"], [], False),
        ([], ["mescola"], False),
        ([], [], False),
    ],
)
def test_completeness_needs_both_a_list_and_a_method(
    ingredients: list[str],
    instructions: list[str],
    *,
    expected: bool,
) -> None:
    """Half an extraction is not something you can cook from."""
    recipe = Recipe(
        code="ABC",
        pk="1",
        post_url=None,
        caption=None,
        title="Torta",
        ingredients=ingredients,
        instructions=instructions,
    )

    assert recipe.is_complete is expected


def test_a_missing_title_does_not_make_a_recipe_incomplete() -> None:
    """Completeness is about the cooking, not the label on the card."""
    recipe = Recipe(
        code="ABC",
        pk="1",
        post_url=None,
        caption=None,
        title=None,
        ingredients=["farina"],
        instructions=["mescola"],
    )

    assert recipe.is_complete is True


def test_completeness_stays_out_of_the_serialised_shape() -> None:
    """Derived on read: it must not become a field that round-trips."""
    recipe = Recipe(
        code="ABC",
        pk="1",
        post_url=None,
        caption=None,
        title="Torta",
        ingredients=["farina"],
        instructions=["mescola"],
    )

    assert "is_complete" not in recipe.model_dump()
    assert Recipe.model_validate(recipe.model_dump()) == recipe


def test_extracted_recipe_without_new_fields_validates() -> None:
    """A pre-v2 extraction payload without the new fields validates via defaults."""
    payload = _extracted().model_dump()
    del payload["course"]
    del payload["mediterranean_categories"]
    del payload["time_is_estimated"]

    extracted = ExtractedRecipe.model_validate(payload)

    assert extracted.course == "unknown"
    assert extracted.mediterranean_categories == []
    assert extracted.time_is_estimated is False


def test_extracted_recipe_without_summary_validates() -> None:
    """A pre-v3 payload without summary still validates, defaulting to empty."""
    payload = _extracted().model_dump()
    del payload["summary"]

    extracted = ExtractedRecipe.model_validate(payload)

    assert extracted.summary == ""


def test_extracted_recipe_without_confidence_defaults_low_not_high() -> None:
    """A stub payload missing confidence must default to 0.0, never high trust."""
    payload = _extracted().model_dump()
    del payload["confidence"]

    extracted = ExtractedRecipe.model_validate(payload)

    assert extracted.confidence == 0.0


def test_extracted_recipe_accepts_yogurt_and_estimated_time() -> None:
    """v3 payloads may carry yogurt as a protein and a flagged time estimate."""
    extracted = _extracted().model_copy(
        update={
            "proteins": ["yogurt"],
            "meal_type": "breakfast",
            "dish_type": "pastry",
            "total_time": "30-60 min",
            "time_is_estimated": True,
        },
    )

    assert extracted.proteins == ["yogurt"]
    assert extracted.meal_type == "breakfast"
    assert extracted.total_time == "30-60 min"
    assert extracted.time_is_estimated is True


def test_extracted_recipe_accepts_summary() -> None:
    """v3 payloads carry an English one-sentence summary for semantic search."""
    extracted = _extracted().model_copy(
        update={"summary": "Classic Roman pasta with guanciale, egg, and pecorino."},
    )

    assert extracted.summary == "Classic Roman pasta with guanciale, egg, and pecorino."


def test_from_extracted_maps_time_is_estimated() -> None:
    """time_is_estimated survives mapping into the domain Recipe."""
    extracted = _extracted().model_copy(
        update={"total_time": "<30 min", "time_is_estimated": True},
    )

    mapped = Recipe.from_extracted(
        code="ABC",
        pk="1",
        caption=None,
        extracted=extracted,
    )

    assert mapped.recipe.total_time == "<30 min"
    assert mapped.recipe.time_is_estimated is True
