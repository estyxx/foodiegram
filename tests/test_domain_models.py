from foodiegram.domain.enums import Course, MedCategory
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


def test_extracted_recipe_without_new_fields_validates() -> None:
    """A pre-v2 extraction payload without the new fields validates via defaults."""
    payload = _extracted().model_dump()
    del payload["course"]
    del payload["mediterranean_categories"]

    extracted = ExtractedRecipe.model_validate(payload)

    assert extracted.course == "unknown"
    assert extracted.mediterranean_categories == []
