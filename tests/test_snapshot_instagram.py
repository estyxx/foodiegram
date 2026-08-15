import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from instagrapi.types import Media, User

from foodiegram.domain.errors import InstagramFetchError
from foodiegram.instagram.cache_manager import CacheManager
from foodiegram.instagram.snapshot import (
    collect_saved_posts,
    default_output_path,
    media_to_item,
    write_snapshot,
)

_CAPTURED_AT = datetime(2026, 8, 15, 10, 0, tzinfo=UTC)
_FULL_MODE_FETCHED = 2
_FULL_MODE_NEW = 1


def _seed_cached_shortcode(cache: CacheManager, *, code: str, pk: str) -> None:
    """Write a minimal valid Media JSON file into the post cache."""
    payload = {
        "pk": pk,
        "id": f"{pk}_0",
        "code": code,
        "taken_at": "2026-01-01T00:00:00+00:00",
        "media_type": 2,
        "like_count": 0,
        "usertags": [],
        "sponsor_tags": [],
        "caption_text": "",
        "user": {
            "pk": "99",
            "username": "chef",
            "full_name": "",
            "is_private": False,
            "profile_pic_url": "https://example.com/x.jpg",
            "is_verified": False,
            "media_count": 0,
            "follower_count": 0,
            "following_count": 0,
            "is_business": False,
        },
    }
    cache.posts_dir.mkdir(parents=True, exist_ok=True)
    path = cache.posts_dir / f"{pk}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")


def _user(*, pk: int, username: str) -> User:
    """Build a minimal User with required instagrapi defaults."""
    return User.model_construct(
        pk=str(pk),
        username=username,
        full_name="",
        is_private=False,
        profile_pic_url="https://example.com/profile.jpg",
        is_verified=False,
        media_count=0,
        follower_count=0,
        following_count=0,
        is_business=False,
    )


def _media(
    *,
    code: str,
    pk: int,
    user_pk: int = 99,
    username: str = "chef",
    caption: str = "pasta",
    media_type: int = 2,
    title: str | None = None,
) -> Media:
    """Build a minimal instagrapi Media object for snapshot tests."""
    return Media.model_construct(
        pk=str(pk),
        code=code,
        media_type=media_type,
        caption_text=caption,
        title=title,
        user=_user(pk=user_pk, username=username),
    )


class _FakeExtractor:
    """Stand-in for InstagramExtractor with scripted collection pages."""

    def __init__(
        self,
        *,
        cache_dir: Path,
        pages: list[list[Media]],
        fail_on_page: int | None = None,
    ) -> None:
        self.cache_manager = CacheManager(cache_dir=cache_dir)
        self._pages = pages
        self._fail_on_page = fail_on_page
        self._page_index = 0

    def fetch_collection_page(
        self,
        *,
        collection_id: str,
        limit: int,
        last_media_pk: int,
    ) -> list[Media]:
        """Return the next scripted page or raise on the configured failure page."""
        _ = collection_id, limit, last_media_pk
        if self._fail_on_page is not None and self._page_index == self._fail_on_page:
            msg = f"rate limited on page {self._page_index}"
            raise InstagramFetchError(msg)

        if self._page_index >= len(self._pages):
            return []

        page = self._pages[self._page_index]
        self._page_index += 1
        return page


def test_default_output_path_uses_timestamp() -> None:
    """Default snapshot paths land under data/ with a timestamp suffix."""
    path = default_output_path(captured_at=_CAPTURED_AT)
    assert path == Path("data/ig_snapshot-20260815-100000.json")


def test_media_to_item_matches_food_json_shape() -> None:
    """Serialized items carry the IGbulkDL field names and dry_run status."""
    media = _media(code="ABC123", pk=111, user_pk=755275224, username="azzuchef")

    item = media_to_item(media=media, captured_at=_CAPTURED_AT)

    assert item == {
        "url": "https://www.instagram.com/p/ABC123/",
        "shortcode": "ABC123",
        "username": "755275224",
        "author": "azzuchef",
        "title": "Video by azzuchef",
        "caption": "pasta",
        "media_type": "video",
        "status": "dry_run",
        "timestamp": _CAPTURED_AT.isoformat(),
    }


def test_collect_saved_posts_incremental_stops_at_cached_shortcode(
    tmp_path: Path,
) -> None:
    """Incremental mode collects one new item then stops before older cached rows."""
    cache = CacheManager(cache_dir=tmp_path / "cache")
    _seed_cached_shortcode(cache, code="OLD1", pk="1")

    extractor = _FakeExtractor(
        cache_dir=tmp_path / "cache",
        pages=[
            [
                _media(code="NEW1", pk=2),
                _media(code="OLD1", pk=1),
            ],
        ],
    )

    result = collect_saved_posts(
        extractor=extractor,  # type: ignore[arg-type]
        collection_id="17854976980356429",
        incremental=True,
    )

    assert result.fetched == 1
    assert result.new_since_last == 1
    assert result.partial is False
    assert [item["shortcode"] for item in result.items] == ["NEW1"]


def test_collect_saved_posts_full_includes_cached_shortcodes(tmp_path: Path) -> None:
    """Full mode keeps paging even when shortcodes are already cached."""
    cache = CacheManager(cache_dir=tmp_path / "cache")
    _seed_cached_shortcode(cache, code="OLD1", pk="1")

    extractor = _FakeExtractor(
        cache_dir=tmp_path / "cache",
        pages=[[_media(code="NEW1", pk=2), _media(code="OLD1", pk=1)]],
    )

    result = collect_saved_posts(
        extractor=extractor,  # type: ignore[arg-type]
        collection_id="17854976980356429",
        incremental=False,
    )

    assert result.fetched == _FULL_MODE_FETCHED
    assert result.new_since_last == _FULL_MODE_NEW
    assert [item["shortcode"] for item in result.items] == ["NEW1", "OLD1"]


def test_collect_saved_posts_partial_failure_keeps_first_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rate-limit on a later page still returns items from earlier pages."""
    monkeypatch.setattr("foodiegram.instagram.snapshot._BATCH_SIZE", 1)
    extractor = _FakeExtractor(
        cache_dir=tmp_path / "cache",
        pages=[[_media(code="NEW1", pk=2)], []],
        fail_on_page=1,
    )

    result = collect_saved_posts(
        extractor=extractor,  # type: ignore[arg-type]
        collection_id="17854976980356429",
        incremental=True,
    )

    assert result.fetched == 1
    assert result.partial is True
    assert result.error_message is not None
    assert [item["shortcode"] for item in result.items] == ["NEW1"]


def test_write_snapshot_matches_food_json_envelope(tmp_path: Path) -> None:
    """Written snapshots include items and summary blocks like food.json."""
    output_path = tmp_path / "snapshot.json"
    items = [media_to_item(media=_media(code="ABC", pk=1), captured_at=_CAPTURED_AT)]

    write_snapshot(output_path=output_path, items=items, captured_at=_CAPTURED_AT)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["items"] == items
    assert payload["summary"]["total_in_file"] == 1
    assert payload["summary"]["dry_run"] == 1
    assert payload["summary"]["last_updated"] == _CAPTURED_AT.isoformat()
