import pytest
from pydantic import ValidationError
from sqlalchemy import Engine

from dispensa.app.save_custom_recipe import build_custom_recipe, save_custom_recipe
from dispensa.domain.enums import RecipeSource
from dispensa.storage.recipes_db import RecipeRepository

_DRAFT: dict[str, object] = {
    "title": "Pasta e ceci",
    "ingredients": ["200g ceci", "160g pasta"],
    "instructions": ["Cook the chickpeas", "Add the pasta"],
    "mediterranean_categories": [{"category": "legumes", "servings": 2.0}],
}


@pytest.fixture
def recipes(db_engine: Engine) -> RecipeRepository:
    """Return a RecipeRepository on the clean test database."""
    return RecipeRepository(db_engine)


def test_build_forces_manual_provenance(recipes: RecipeRepository) -> None:
    """Confirm a built custom recipe is MANUAL, has no post_url, and a m- code."""
    recipe = build_custom_recipe(dict(_DRAFT), recipes=recipes)

    assert recipe.source is RecipeSource.MANUAL
    assert recipe.post_url is None
    assert recipe.code.startswith("m-pasta-e-ceci-")
    assert [c.source for c in recipe.mediterranean_categories] == ["manual"]


def test_build_records_inspired_by(recipes: RecipeRepository) -> None:
    """Carry inspired_by codes through onto the recipe (D24: any post)."""
    recipe = build_custom_recipe(
        {**_DRAFT, "inspired_by": ["DJq4i8ysCL8", "m-other-AB12"]},
        recipes=recipes,
    )

    assert recipe.inspired_by == ["DJq4i8ysCL8", "m-other-AB12"]


def test_build_rejects_a_draft_missing_required_fields(
    recipes: RecipeRepository,
) -> None:
    """Reject a draft without instructions."""
    bad = {key: value for key, value in _DRAFT.items() if key != "instructions"}

    with pytest.raises(ValidationError):
        build_custom_recipe(bad, recipes=recipes)


def test_save_persists_and_returns_the_recipe(recipes: RecipeRepository) -> None:
    """Write the recipe and read it back by code."""
    saved = save_custom_recipe(dict(_DRAFT), recipes=recipes)

    stored = recipes.get(saved.code)
    assert stored is not None
    assert stored.title == "Pasta e ceci"
    assert stored.source is RecipeSource.MANUAL


def test_generated_codes_are_unique_per_title(recipes: RecipeRepository) -> None:
    """Give two saves of the same title distinct codes."""
    first = save_custom_recipe(dict(_DRAFT), recipes=recipes)
    second = save_custom_recipe(dict(_DRAFT), recipes=recipes)

    assert first.code != second.code
