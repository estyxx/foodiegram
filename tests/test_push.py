from sqlalchemy import Engine

from dispensa.app.push import push_recipes
from dispensa.domain.editing import apply_push
from dispensa.domain.enums import MedCategory, RecipeSource
from dispensa.domain.models import CategoryServing, Recipe
from dispensa.domain.pantry import PantryItem
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.recipes_db import RecipeRepository

_KEPT_ON_TARGET = 2


def _recipe(
    code: str,
    *,
    title: str = "Title",
    total_time: str | None = "20 min",
    caption: str = "caption",
    source: RecipeSource = RecipeSource.INSTAGRAM,
    edited: frozenset[str] = frozenset(),
) -> Recipe:
    """Build a minimal recipe for push tests."""
    return Recipe(
        code=code,
        source=source,
        pk="1",
        post_url=f"https://instagram.com/p/{code}/",
        caption=caption,
        title=title,
        ingredients=["200g salmon"],
        instructions=["cook"],
        mediterranean_categories=[CategoryServing(category=MedCategory.FISH)],
        total_time=total_time,
        edited_fields=edited,
        prompt_version="3",
    )


# --- apply_push (pure domain) ---


def test_apply_push_overlays_non_edited_extraction_fields() -> None:
    """A field the target has not edited takes the source's value."""
    target = _recipe("X", total_time="10 min")
    source = _recipe("X", total_time="30 min")

    assert apply_push(target, source).total_time == "30 min"


def test_apply_push_keeps_edited_and_protected_fields() -> None:
    """An edited field and a protected field (caption) keep the target's value."""
    target = _recipe("X", title="user", caption="orig", edited=frozenset({"title"}))
    source = _recipe("X", title="extracted", caption="changed")

    merged = apply_push(target, source)

    assert merged.title == "user"
    assert merged.caption == "orig"


# --- push_recipes (through the Postgres test databases) ---


def test_push_inserts_a_recipe_the_target_lacks(
    db_engine: Engine,
    target_engine: Engine,
) -> None:
    """A source Instagram recipe missing on the target is inserted."""
    source = RecipeRepository(db_engine)
    target = RecipeRepository(target_engine)
    source.save(_recipe("AAA111", title="New"))

    report = push_recipes(source=source, target=target, dry_run=False)

    assert report.inserted == ["AAA111"]
    assert target.get("AAA111") is not None


def test_push_updates_only_fields_the_target_has_not_edited(
    db_engine: Engine,
    target_engine: Engine,
) -> None:
    """On a recipe present on both, edited fields survive; others take the source."""
    source = RecipeRepository(db_engine)
    target = RecipeRepository(target_engine)
    target.save(
        _recipe(
            "BBB222",
            title="User title",
            total_time="10 min",
            edited=frozenset({"title"}),
        ),
    )
    source.save(_recipe("BBB222", title="Extracted title", total_time="30 min"))

    report = push_recipes(source=source, target=target, dry_run=False)

    assert report.updated == ["BBB222"]
    pushed = target.get("BBB222")
    assert pushed is not None
    assert pushed.title == "User title"
    assert pushed.total_time == "30 min"


def test_push_never_touches_manual_recipes_or_other_tables(
    db_engine: Engine,
    target_engine: Engine,
) -> None:
    """Manual and target-only recipes stay; nothing is deleted; pantry is untouched."""
    source = RecipeRepository(db_engine)
    target = RecipeRepository(target_engine)
    target.save(_recipe("m-own-1", title="My own", source=RecipeSource.MANUAL))
    target.save(_recipe("CCC333", title="Only on target"))
    pantry = PantryRepository(target_engine)
    pantry.add(PantryItem(name="ceci", kind="staple"))
    source.save(_recipe("DDD444", title="New"))

    report = push_recipes(source=source, target=target, dry_run=False)

    assert report.inserted == ["DDD444"]
    assert report.target_only_kept == _KEPT_ON_TARGET
    manual = target.get("m-own-1")
    assert manual is not None
    assert manual.title == "My own"
    assert target.get("CCC333") is not None
    assert len(pantry.list_all()) == 1


def test_push_dry_run_writes_nothing(
    db_engine: Engine,
    target_engine: Engine,
) -> None:
    """A dry run reports the insert but persists nothing to the target."""
    source = RecipeRepository(db_engine)
    target = RecipeRepository(target_engine)
    source.save(_recipe("EEE555", title="New"))

    report = push_recipes(source=source, target=target, dry_run=True)

    assert report.inserted == ["EEE555"]
    assert target.get("EEE555") is None
