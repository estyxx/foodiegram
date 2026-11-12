from collections.abc import Callable

import pytest
from sqlalchemy import Engine

from dispensa.app.revert_field import revert_recipe_field
from dispensa.domain.enums import RecipeSource
from dispensa.domain.errors import ExtractionError, RecipeNotFoundError
from dispensa.domain.models import ExtractedRecipe, Extraction, Recipe
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.recipes_db import RecipeRepository

_CODE = "ABC12345678"


@pytest.fixture
def recipes(db_engine: Engine) -> RecipeRepository:
    """Return a RecipeRepository on the clean test database."""
    return RecipeRepository(db_engine)


@pytest.fixture
def extractions(db_engine: Engine) -> ExtractionRepository:
    """Return an ExtractionRepository on the clean test database."""
    return ExtractionRepository(db_engine)


def _edited_recipe() -> Recipe:
    """Build a recipe whose title was hand-edited away from the extracted value."""
    return Recipe(
        code=_CODE,
        source=RecipeSource.INSTAGRAM,
        pk="99",
        post_url=f"https://instagram.com/p/{_CODE}/",
        caption="Original caption",
        title="My title",
        ingredients=["user ingredient"],
        instructions=["step"],
        edited_fields=frozenset({"title"}),
        prompt_version="2",
        model_used="gpt-test",
    )


def test_revert_restores_extracted_value_and_clears_marker(
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
    make_extracted: Callable[..., ExtractedRecipe],
    make_extraction: Callable[..., Extraction],
) -> None:
    """Revert restores the extracted title and drops it from edited_fields."""
    recipes.save(_edited_recipe())
    extractions.add(
        make_extraction(code=_CODE, payload=make_extracted(title="Extracted title")),
    )

    reverted = revert_recipe_field(
        _CODE,
        field="title",
        recipes=recipes,
        extractions=extractions,
    )

    assert reverted.title == "Extracted title"
    assert reverted.edited_fields == frozenset()
    stored = recipes.get(_CODE)
    assert stored is not None
    assert stored.title == "Extracted title"


def test_revert_raises_without_an_extraction(
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
) -> None:
    """A recipe with no extraction cannot revert a field."""
    recipes.save(_edited_recipe())

    with pytest.raises(ExtractionError, match="no extraction"):
        revert_recipe_field(
            _CODE,
            field="title",
            recipes=recipes,
            extractions=extractions,
        )


def test_revert_raises_for_unknown_recipe(
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
) -> None:
    """An unknown code raises before anything is read from extractions."""
    with pytest.raises(RecipeNotFoundError):
        revert_recipe_field(
            "nope",
            field="title",
            recipes=recipes,
            extractions=extractions,
        )
