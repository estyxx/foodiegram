import importlib.util
from pathlib import Path
from types import ModuleType

from foodiegram.domain.models import Recipe

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
_EXPIRED_CDN = "https://scontent-man2-1.cdninstagram.com/v/t51.png?oh=sig&oe=exp"
_DURABLE = "https://res.cloudinary.com/demo/image/upload/foodiegram/ABC.jpg"


def _load_script(name: str) -> ModuleType:
    """Import a loose scripts/ module by file path (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _recipe(
    *,
    code: str = "ABC",
    caption: str | None = None,
    thumbnail_url: str | None = None,
    cloudinary_url: str | None = None,
) -> Recipe:
    """Build a minimal Recipe with the given image-related fields."""
    return Recipe(
        code=code,
        pk="1",
        post_url=f"https://instagram.com/p/{code}/",
        caption=caption,
        title="Test",
        ingredients=[],
        instructions=[],
        thumbnail_url=thumbnail_url,
        cloudinary_url=cloudinary_url,
    )


def test_upload_thumbnails_selection_unchanged() -> None:
    """upload_thumbnails targets captionless recipes with a source but no durable URL."""
    mod = _load_script("upload_thumbnails")

    eligible = _recipe(thumbnail_url="https://src/x.jpg")
    assert mod.upload_source(eligible) == "https://src/x.jpg"

    assert mod.upload_source(_recipe(thumbnail_url="x", cloudinary_url=_DURABLE)) is None
    assert mod.upload_source(_recipe(thumbnail_url="x", caption="hi")) is None
    assert mod.upload_source(_recipe(thumbnail_url=None)) is None


def test_upload_thumbnails_writes_only_cloudinary_url() -> None:
    """upload_thumbnails writes cloudinary_url and leaves thumbnail_url untouched."""
    mod = _load_script("upload_thumbnails")
    recipe = _recipe(thumbnail_url="https://src/x.jpg")

    updated = mod.with_uploaded(recipe, secure_url=_DURABLE)

    assert updated.cloudinary_url == _DURABLE
    assert updated.thumbnail_url == "https://src/x.jpg"


def test_fix_cdn_selection_unchanged() -> None:
    """fix_cdn_thumbnails still targets only expired-CDN thumbnails."""
    mod = _load_script("fix_cdn_thumbnails")

    assert mod.is_broken(_recipe(thumbnail_url=_EXPIRED_CDN)) is True
    assert mod.is_broken(_recipe(thumbnail_url=_DURABLE)) is False
    assert (
        mod.is_broken(_recipe(thumbnail_url="https://www.instagram.com/p/ABC/media/"))
        is False
    )
    assert mod.is_broken(_recipe(thumbnail_url=None)) is False


def test_fix_cdn_writes_both_thumbnail_and_cloudinary_url() -> None:
    """fix_cdn_thumbnails rewrites thumbnail_url to stable and sets cloudinary_url."""
    mod = _load_script("fix_cdn_thumbnails")
    recipe = _recipe(thumbnail_url=_EXPIRED_CDN)
    stable = "https://www.instagram.com/p/ABC/media/?size=l"

    updated = mod.with_uploaded(recipe, stable_url=stable, secure_url=_DURABLE)

    assert updated.thumbnail_url == stable
    assert updated.cloudinary_url == _DURABLE
