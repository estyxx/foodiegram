from pathlib import Path

from sqlalchemy import Engine

from foodiegram.app.ingest import (
    STABLE_MEDIA_URL,
    DedupeReport,
    FoodItem,
    dedupe_links,
    ingest_food_json,
)
from foodiegram.domain.hashing import caption_hash
from foodiegram.domain.models import Recipe
from foodiegram.images import UploadedImage
from foodiegram.storage._tables import RecipeRow
from foodiegram.storage.db import get_session
from foodiegram.storage.recipes_db import RecipeRepository

_VALID_CLOUDINARY = "https://res.cloudinary.com/demo/image/upload/foodiegram/{code}.jpg"


class _FakeUploader:
    """Records upload calls and returns a deterministic durable URL."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(
        self,
        *,
        shortcode: str,
        source_url_or_path: str,
        overwrite: bool = True,
    ) -> UploadedImage:
        """Record the shortcode and return a fake Cloudinary result."""
        _ = (source_url_or_path, overwrite)
        self.calls.append(shortcode)
        return UploadedImage(
            public_id=f"foodiegram/{shortcode}",
            secure_url=f"https://res.cloudinary.com/x/{shortcode}.jpg",
        )


def _item(
    shortcode: str,
    *,
    author: str | None = "chef",
    caption: str | None = None,
    title: str | None = None,
) -> FoodItem:
    """Build a FoodItem with a stable thumbnail source."""
    return FoodItem(
        shortcode=shortcode,
        pk="1",
        author=author,
        caption=caption,
        title=title,
        thumbnail_url=STABLE_MEDIA_URL.format(code=shortcode),
    )


def _recipe(code: str, *, caption: str | None, cloudinary_url: str | None) -> Recipe:
    """Build a stored recipe with an explicit caption and durable image."""
    return Recipe(
        code=code,
        pk="1",
        post_url=None,
        caption=caption,
        title="Stored",
        ingredients=[],
        instructions=[],
        cloudinary_url=cloudinary_url,
    )


def _stored_caption_hash(engine: Engine, code: str) -> str | None:
    """Read the persisted caption_hash column for one recipe."""
    with get_session(engine) as session:
        row = session.get(RecipeRow, code)
    assert row is not None
    return row.caption_hash


def test_dedupe_links_drops_duplicates_and_known(engine: Engine, tmp_path: Path) -> None:
    """Duplicate shortcodes and codes already in the DB are removed."""
    repo = RecipeRepository(engine)
    repo.save(_recipe("INDB1", caption=None, cloudinary_url=None))
    links = tmp_path / "links.txt"
    links.write_text(
        "https://www.instagram.com/p/NEW1/\n"
        "https://www.instagram.com/p/NEW1/\n"
        "https://www.instagram.com/p/NEW2/\n"
        "https://www.instagram.com/p/INDB1/\n"
        "\n",
        encoding="utf-8",
    )

    report = dedupe_links(
        links_file=links,
        known_codes={r.code for r in repo.list_all()},
    )

    assert report == DedupeReport(
        read=4,
        unique=3,
        already_in_db=1,
        written_urls=(
            "https://www.instagram.com/p/NEW1/",
            "https://www.instagram.com/p/NEW2/",
        ),
    )


def test_ingest_new_item_persists_author_and_caption_hash(engine: Engine) -> None:
    """A new item creates a stub with author + caption_hash and uploads its image."""
    repo = RecipeRepository(engine)
    uploader = _FakeUploader()
    item = _item("NEW1", author="mario", caption="a long enough caption for a recipe")

    report = ingest_food_json(
        recipes=repo,
        items=[item],
        upload=uploader,
        dry_run=False,
    )

    result = report.results[0]
    assert result.is_new
    assert result.image_fixed
    assert not result.caption_changed
    assert uploader.calls == ["NEW1"]
    stored = repo.get("NEW1")
    assert stored is not None
    assert stored.author_username == "mario"
    assert stored.cloudinary_url == "https://res.cloudinary.com/x/NEW1.jpg"
    assert _stored_caption_hash(engine, "NEW1") == caption_hash(item.caption)
    assert report.codes_needing_extraction == ["NEW1"]


def test_ingest_unchanged_item_neither_writes_nor_uploads(engine: Engine) -> None:
    """A known item with the same caption and a valid image is skipped."""
    repo = RecipeRepository(engine)
    caption = "identical caption text stored already"
    image = _VALID_CLOUDINARY.format(code="K1")
    repo.save(_recipe("K1", caption=caption, cloudinary_url=image))
    uploader = _FakeUploader()

    report = ingest_food_json(
        recipes=repo,
        items=[_item("K1", caption=caption)],
        upload=uploader,
        dry_run=False,
    )

    result = report.results[0]
    assert result.unchanged
    assert uploader.calls == []
    assert report.codes_needing_extraction == []


def test_ingest_changed_caption_updates_caption_and_hash(engine: Engine) -> None:
    """A different caption on a known recipe refreshes caption and caption_hash."""
    repo = RecipeRepository(engine)
    repo.save(
        _recipe(
            "K2",
            caption="old caption text",
            cloudinary_url=_VALID_CLOUDINARY.format(code="K2"),
        ),
    )
    uploader = _FakeUploader()
    new_caption = "brand new caption text"

    report = ingest_food_json(
        recipes=repo,
        items=[_item("K2", caption=new_caption)],
        upload=uploader,
        dry_run=False,
    )

    result = report.results[0]
    assert result.caption_changed
    assert not result.is_new
    assert uploader.calls == []
    stored = repo.get("K2")
    assert stored is not None
    assert stored.caption == new_caption
    assert _stored_caption_hash(engine, "K2") == caption_hash(new_caption)


def test_ingest_broken_image_triggers_upload(engine: Engine) -> None:
    """A known recipe with no durable image is (re)uploaded via the adapter."""
    repo = RecipeRepository(engine)
    caption = "same caption text kept unchanged"
    repo.save(_recipe("K3", caption=caption, cloudinary_url=None))
    uploader = _FakeUploader()

    report = ingest_food_json(
        recipes=repo,
        items=[_item("K3", caption=caption)],
        upload=uploader,
        dry_run=False,
    )

    result = report.results[0]
    assert result.image_fixed
    assert not result.caption_changed
    assert not result.is_new
    assert uploader.calls == ["K3"]
    stored = repo.get("K3")
    assert stored is not None
    assert stored.cloudinary_url == "https://res.cloudinary.com/x/K3.jpg"


def test_ingest_dry_run_reports_without_writing(engine: Engine) -> None:
    """Dry-run flags the work but persists nothing and calls no uploader."""
    repo = RecipeRepository(engine)
    uploader = _FakeUploader()

    report = ingest_food_json(
        recipes=repo,
        items=[_item("DRY1", caption="a caption for a dry run item")],
        upload=uploader,
        dry_run=True,
    )

    result = report.results[0]
    assert result.is_new
    assert result.image_fixed
    assert uploader.calls == []
    assert repo.get("DRY1") is None
