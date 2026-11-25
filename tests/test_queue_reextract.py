from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest
from sqlalchemy import Engine

from dispensa.app.queue import queue_link, set_queued_caption
from dispensa.app.queue_import import embed_imported, upload_imported_images
from dispensa.app.queue_reextract import reextract_queued
from dispensa.domain.editing import apply_user_edit
from dispensa.domain.enums import PendingStatus
from dispensa.domain.errors import ExtractionError, PendingLinkNotFoundError
from dispensa.domain.models import ExtractedCategoryServing, ExtractedRecipe
from dispensa.images import UploadedImage
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pending_db import PendingLinkRepository
from dispensa.storage.recipes_db import RecipeRepository

if TYPE_CHECKING:
    from openai import OpenAI

_QUEUED_AT = datetime(2026, 11, 1, tzinfo=UTC)
_NOW = datetime(2026, 11, 25, 22, 0, tzinfo=UTC)
_URL = "https://www.instagram.com/p/ABC123/"


def _extracted(title: str) -> ExtractedRecipe:
    """Build a minimal valid extraction titled title."""
    return ExtractedRecipe(
        title=title,
        ingredients=["300g zucca", "160g pasta"],
        instructions=["cuoci", "manteca"],
        dish_type="pasta",
        meal_type="lunch",
        cuisine_type="italian",
        difficulty="easy",
        course="primo",
        mediterranean_categories=[ExtractedCategoryServing(category="dairy")],
        proteins=[],
        vegetables=["pumpkin"],
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


class _Extractor:
    """Stand in for the AI: returns a fixed recipe and records the input."""

    def __init__(self, title: str = "Pasta e zucca") -> None:
        self.title = title
        self.inputs: list[str] = []

    def __call__(self, caption: str, /) -> ExtractedRecipe:
        """Record caption and return the fixed extraction."""
        self.inputs.append(caption)
        return _extracted(self.title)


def _failing(_caption: str, /) -> ExtractedRecipe:
    """Stand in for an AI call that does not come back."""
    msg = "The extraction did not come back."
    raise ExtractionError(msg)


@dataclass(frozen=True)
class _Store:
    pending: PendingLinkRepository
    recipes: RecipeRepository
    extractions: ExtractionRepository


@pytest.fixture
def store(db_engine: Engine) -> _Store:
    """Build a queue holding one captioned link, ABC123, not yet extracted."""
    built = _Store(
        pending=PendingLinkRepository(db_engine),
        recipes=RecipeRepository(db_engine),
        extractions=ExtractionRepository(db_engine),
    )
    queue_link(url=_URL, now=_QUEUED_AT, pending=built.pending, recipes=built.recipes)
    set_queued_caption(code="ABC123", caption="Original caption", pending=built.pending)
    return built


def _reextract(store: _Store, *, caption: str, extract: object) -> object:
    """Run the use-case against the store."""
    return reextract_queued(
        code="ABC123",
        caption=caption,
        now=_NOW,
        pending=store.pending,
        recipes=store.recipes,
        extractions=store.extractions,
        extract=cast("_Extractor", extract),
    )


def test_extracting_a_ready_link_now_makes_the_recipe(store: _Store) -> None:
    """A link need not wait for a batch: it becomes a recipe at once."""
    extract = _Extractor()

    _reextract(store, caption="  Pasta e zucca: 300g zucca  ", extract=extract)

    recipe = store.recipes.get("ABC123")
    link = store.pending.get("ABC123")
    assert recipe is not None
    assert recipe.title == "Pasta e zucca"
    assert recipe.caption == "Pasta e zucca: 300g zucca"
    assert extract.inputs == ["Pasta e zucca: 300g zucca"]
    assert link is not None
    assert link.status is PendingStatus.IMPORTED
    assert link.imported_at == _NOW


def test_reextracting_keeps_what_the_owner_edited(store: _Store) -> None:
    """New notes re-extract the recipe, but a hand-edited title stays."""
    _reextract(store, caption="First text", extract=_Extractor(title="Wrong title"))
    first = store.recipes.get("ABC123")
    assert first is not None
    store.recipes.save(apply_user_edit(first, {"title": "My title"}))

    _reextract(
        store, caption="Notes: ingredients from the comments", extract=_Extractor()
    )

    recipe = store.recipes.get("ABC123")
    assert recipe is not None
    assert recipe.title == "My title"
    assert recipe.caption == "Notes: ingredients from the comments"
    history = [
        e for e in store.extractions.for_version("3") if e.recipe_code == "ABC123"
    ]
    assert [e.kind for e in history] == ["repair", "repair"]


def test_a_failed_extraction_changes_nothing(store: _Store) -> None:
    """When the AI call fails, the caption and the queue stay as they were."""
    with pytest.raises(ExtractionError):
        _reextract(store, caption="New notes", extract=_failing)

    link = store.pending.get("ABC123")
    assert link is not None
    assert link.caption == "Original caption"
    assert link.status is PendingStatus.READY
    assert store.recipes.get("ABC123") is None


def test_an_empty_caption_is_refused(store: _Store) -> None:
    """There must be something to extract from."""
    with pytest.raises(ValueError, match="empty"):
        _reextract(store, caption="   ", extract=_Extractor())


def test_an_unknown_link_is_refused(store: _Store) -> None:
    """Only a queued link can be re-extracted."""
    with pytest.raises(PendingLinkNotFoundError):
        reextract_queued(
            code="NOPE",
            caption="x",
            now=_NOW,
            pending=store.pending,
            recipes=store.recipes,
            extractions=store.extractions,
            extract=_Extractor(),
        )


@dataclass
class _Item:
    index: int
    embedding: list[float]


@dataclass
class _Response:
    data: list[_Item]


@dataclass
class _Embeddings:
    calls: list[list[str]] = field(default_factory=list)

    def create(self, *, input: list[str], model: str) -> _Response:  # noqa: A002
        """Return one vector per input, recording the batch."""
        _ = model
        self.calls.append(input)
        return _Response(
            data=[_Item(index=i, embedding=[1.0, 0.0]) for i in range(len(input))]
        )


@dataclass
class _OpenAI:
    embeddings: _Embeddings = field(default_factory=_Embeddings)


def test_imported_recipes_are_embedded_once(store: _Store) -> None:
    """Imports become searchable (and visible to Claude); fresh ones are skipped."""
    _reextract(store, caption="Pasta e zucca", extract=_Extractor())
    client = _OpenAI()

    first = embed_imported(
        pending=store.pending,
        recipes=store.recipes,
        client=cast("OpenAI", client),
    )
    again = embed_imported(
        pending=store.pending,
        recipes=store.recipes,
        client=cast("OpenAI", client),
    )

    assert first == 1
    assert again == 0
    assert store.recipes.get_embedding("ABC123") is not None


class _Uploader:
    """Stand in for Cloudinary: records each upload and returns a durable URL."""

    def __init__(self) -> None:
        self.sources: list[str] = []

    def __call__(
        self,
        *,
        shortcode: str,
        source_url_or_path: str,
        overwrite: bool = True,
    ) -> UploadedImage:
        """Record the source and return a fake Cloudinary copy."""
        _ = overwrite
        self.sources.append(source_url_or_path)
        return UploadedImage(
            public_id=shortcode,
            secure_url=f"https://res.cloudinary.com/demo/{shortcode}.jpg",
        )


def test_imported_recipes_get_a_durable_image_once(store: _Store) -> None:
    """A queue import gets a Cloudinary copy of the post's public image."""
    _reextract(store, caption="Pasta e zucca", extract=_Extractor())
    upload = _Uploader()

    first = upload_imported_images(
        pending=store.pending, recipes=store.recipes, upload=upload
    )
    again = upload_imported_images(
        pending=store.pending, recipes=store.recipes, upload=upload
    )

    recipe = store.recipes.get("ABC123")
    assert first == 1
    assert again == 0
    assert upload.sources == ["https://www.instagram.com/p/ABC123/media/?size=l"]
    assert recipe is not None
    assert recipe.cloudinary_url == "https://res.cloudinary.com/demo/ABC123.jpg"
