from collections.abc import Callable

from sqlalchemy import Engine

from foodiegram.app.diff_batch import diff_versions
from foodiegram.domain.models import ExtractedRecipe, Extraction, Recipe
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.recipes_db import RecipeRepository


def _recipe_stub(code: str) -> Recipe:
    """Build a minimal recipe row so extractions satisfy the FK."""
    return Recipe(
        code=code,
        pk="1",
        post_url=None,
        caption=None,
        title="Stub",
        ingredients=["water"],
        instructions=["boil"],
    )


def test_diff_versions_reports_changed_fields(
    db_engine: Engine,
    make_extracted: Callable[..., ExtractedRecipe],
    make_extraction: Callable[..., Extraction],
) -> None:
    """Only recipes present at both versions are compared; changed fields counted."""
    recipes = RecipeRepository(db_engine)
    for code in ("ABC", "XYZ"):
        recipes.save(_recipe_stub(code))

    extractions = ExtractionRepository(db_engine)
    extractions.add(
        make_extraction(
            code="ABC",
            payload=make_extracted(dish_type="pasta"),
            version="1",
        ),
    )
    extractions.add(
        make_extraction(
            code="ABC",
            payload=make_extracted(dish_type="risotto"),
            version="2",
        ),
    )
    extractions.add(
        make_extraction(
            code="XYZ",
            payload=make_extracted(dish_type="pasta"),
            version="1",
        ),
    )

    report = diff_versions(extractions=extractions, from_version="1", to_version="2")
    assert report.compared == 1
    assert report.changed == 1
    assert report.field_counts.get("dish_type") == 1


def test_diff_versions_field_filter(
    db_engine: Engine,
    make_extracted: Callable[..., ExtractedRecipe],
    make_extraction: Callable[..., Extraction],
) -> None:
    """The field filter restricts the diff to a single field."""
    RecipeRepository(db_engine).save(_recipe_stub("ABC"))

    extractions = ExtractionRepository(db_engine)
    extractions.add(
        make_extraction(
            code="ABC",
            payload=make_extracted(dish_type="pasta"),
            version="1",
        ),
    )
    extractions.add(
        make_extraction(
            code="ABC",
            payload=make_extracted(dish_type="risotto"),
            version="2",
        ),
    )

    report = diff_versions(
        extractions=extractions,
        from_version="1",
        to_version="2",
        field="title",
    )
    assert report.changed == 0
