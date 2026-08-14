from collections.abc import Callable

from sqlalchemy import Engine, text
from sqlmodel import Session

from foodiegram.app.promotion import promote_version
from foodiegram.domain.models import ExtractedRecipe, Extraction, Recipe
from foodiegram.storage._tables import ExtractionRow
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.recipes_db import RecipeRepository


def _stub_recipe(
    *,
    code: str,
    edited_fields: frozenset[str] = frozenset(),
    edited_by_user: bool = False,
) -> Recipe:
    """Build a minimally-populated recipe stub awaiting promotion."""
    return Recipe(
        code=code,
        pk="1",
        post_url=f"https://instagram.com/p/{code}/",
        caption="A caption long enough to be a real recipe post about some food.",
        title="Old Title",
        ingredients=["old ingredient"],
        instructions=[],
        edited_fields=edited_fields,
        edited_by_user=edited_by_user,
    )


def test_promote_updates_recipe_and_preserves_user_edits(
    db_engine: Engine,
    make_extracted: Callable[..., ExtractedRecipe],
    make_extraction: Callable[..., Extraction],
) -> None:
    """Promotion updates classification, keeps user-edited fields, and is idempotent."""
    recipes = RecipeRepository(db_engine)
    extractions = ExtractionRepository(db_engine)

    recipes.save(
        _stub_recipe(
            code="ABC",
            edited_fields=frozenset({"ingredients"}),
            edited_by_user=True,
        ),
    )
    extractions.add(
        make_extraction(
            code="ABC",
            payload=make_extracted(title="New Title", ingredients=["new ingredient"]),
        ),
    )

    dry = promote_version(
        recipes=recipes,
        extractions=extractions,
        version="2",
        dry_run=True,
    )
    assert dry.changed == 1
    assert dry.promoted == 0
    change = dry.changes[0]
    changed_fields = {diff.field for diff in change.diffs}
    assert "title" in changed_fields
    assert "ingredients" not in changed_fields
    assert change.skipped_fields == ("ingredients",)
    before = recipes.get("ABC")
    assert before is not None
    assert before.title == "Old Title"  # dry-run persisted nothing

    applied = promote_version(
        recipes=recipes,
        extractions=extractions,
        version="2",
        dry_run=False,
    )
    assert applied.promoted == 1
    saved = recipes.get("ABC")
    assert saved is not None
    assert saved.title == "New Title"
    assert saved.ingredients == ["old ingredient"]

    again = promote_version(
        recipes=recipes,
        extractions=extractions,
        version="2",
        dry_run=True,
    )
    assert again.changed == 0


def test_promote_counts_extractions_without_a_recipe(
    db_engine: Engine,
    make_extracted: Callable[..., ExtractedRecipe],
    make_extraction: Callable[..., Extraction],
) -> None:
    """An extraction whose recipe is absent is reported, not promoted."""
    extractions = ExtractionRepository(db_engine)
    orphan = make_extraction(code="GHOST", payload=make_extracted())
    with Session(db_engine) as session:
        session.connection().execute(text("SET session_replication_role = replica"))
        session.add(
            ExtractionRow(
                recipe_code=orphan.recipe_code,
                prompt_version=orphan.prompt_version,
                model=orphan.model,
                batch_id=orphan.batch_id,
                kind=orphan.kind,
                extracted_at=orphan.extracted_at,
                payload=orphan.payload.model_dump(mode="json"),
            ),
        )
        session.commit()

    report = promote_version(
        recipes=RecipeRepository(db_engine),
        extractions=extractions,
        version="2",
        dry_run=True,
    )
    assert report.considered == 0
    assert report.missing_recipe == 1
