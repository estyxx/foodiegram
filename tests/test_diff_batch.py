from collections.abc import Callable

from sqlalchemy import Engine

from foodiegram.app.diff_batch import diff_versions
from foodiegram.domain.models import ExtractedRecipe, Extraction
from foodiegram.storage.extractions_db import ExtractionRepository


def test_diff_versions_reports_changed_fields(
    db_engine: Engine,
    make_extracted: Callable[..., ExtractedRecipe],
    make_extraction: Callable[..., Extraction],
) -> None:
    """Only recipes present at both versions are compared; changed fields counted."""
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
