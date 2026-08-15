import cloudinary.uploader
import pytest

from foodiegram.domain.errors import ImageUploadError
from foodiegram.images import (
    UploadedImage,
    is_expired_cdn_url,
    is_valid_image_ref,
    upload_thumbnail,
)

_EXPIRED_CDN = "https://scontent-man2-1.cdninstagram.com/v/t51.png?oh=sig&oe=exp"
_DURABLE = "https://res.cloudinary.com/demo/image/upload/foodiegram/ABC.jpg"
_STABLE_SOURCE = "https://www.instagram.com/p/ABC/media/?size=l"


class _FakeUploader:
    """Records Cloudinary upload calls and returns a canned response or raises."""

    def __init__(
        self,
        *,
        response: dict[str, object] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.calls: list[dict[str, object]] = []
        self._response = response
        self._error = error

    def __call__(
        self,
        source: str,
        *,
        public_id: str,
        folder: str,
        overwrite: bool,
        resource_type: str,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "source": source,
                "public_id": public_id,
                "folder": folder,
                "overwrite": overwrite,
                "resource_type": resource_type,
            },
        )
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


@pytest.mark.parametrize("ref", [None, "", "   ", _EXPIRED_CDN])
def test_is_valid_image_ref_rejects_missing_or_expired(ref: str | None) -> None:
    """Null, empty, and expired-CDN refs are not usable images."""
    assert is_valid_image_ref(ref) is False


@pytest.mark.parametrize("ref", [_DURABLE, _STABLE_SOURCE])
def test_is_valid_image_ref_accepts_durable_and_stable(ref: str) -> None:
    """A durable Cloudinary URL and the stable /media source are usable images."""
    assert is_valid_image_ref(ref) is True


def test_is_expired_cdn_url_matches_only_the_cdn_prefix() -> None:
    """Only the signed Instagram CDN host counts as expired/broken."""
    assert is_expired_cdn_url(_EXPIRED_CDN) is True
    assert is_expired_cdn_url(_DURABLE) is False
    assert is_expired_cdn_url(_STABLE_SOURCE) is False


def test_upload_thumbnail_returns_durable_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A successful upload returns the durable URL and public_id, one SDK call."""
    fake = _FakeUploader(
        response={"secure_url": _DURABLE, "public_id": "foodiegram/ABC"},
    )
    monkeypatch.setattr(cloudinary.uploader, "upload", fake)

    result = upload_thumbnail(shortcode="ABC", source_url_or_path=_STABLE_SOURCE)

    assert result == UploadedImage(public_id="foodiegram/ABC", secure_url=_DURABLE)
    assert len(fake.calls) == 1
    assert fake.calls[0]["source"] == _STABLE_SOURCE
    assert fake.calls[0]["public_id"] == "ABC"


def test_upload_thumbnail_same_shortcode_replaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public_id is the shortcode every time, so re-uploads replace not duplicate."""
    fake = _FakeUploader(
        response={"secure_url": _DURABLE, "public_id": "foodiegram/ABC"},
    )
    monkeypatch.setattr(cloudinary.uploader, "upload", fake)

    upload_thumbnail(shortcode="ABC", source_url_or_path="one")
    upload_thumbnail(shortcode="ABC", source_url_or_path="two")

    assert [call["public_id"] for call in fake.calls] == ["ABC", "ABC"]
    assert [call["overwrite"] for call in fake.calls] == [True, True]


def test_upload_thumbnail_raises_on_sdk_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raising SDK is wrapped in a typed ImageUploadError."""
    fake = _FakeUploader(error=RuntimeError("network down"))
    monkeypatch.setattr(cloudinary.uploader, "upload", fake)

    with pytest.raises(ImageUploadError):
        upload_thumbnail(shortcode="ABC", source_url_or_path="x")


def test_upload_thumbnail_raises_on_incomplete_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A response missing secure_url/public_id is a typed failure, not a half-result."""
    fake = _FakeUploader(response={"secure_url": _DURABLE})
    monkeypatch.setattr(cloudinary.uploader, "upload", fake)

    with pytest.raises(ImageUploadError):
        upload_thumbnail(shortcode="ABC", source_url_or_path="x")
