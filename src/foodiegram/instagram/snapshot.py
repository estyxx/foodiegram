import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from instagrapi.types import Media

from foodiegram.domain.errors import InstagramFetchError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from foodiegram.instagram.cache_manager import CacheManager
    from foodiegram.instagram.extractor import InstagramExtractor

logger = logging.getLogger(__name__)

_BATCH_SIZE = 100

_MEDIA_TYPE_LABELS: dict[int, str] = {
    1: "image",
    2: "video",
    8: "carousel",
}


@dataclass(frozen=True)
class SnapshotResult:
    """Outcome of a saved-post snapshot run."""

    items: tuple[dict[str, object], ...]
    fetched: int
    new_since_last: int
    partial: bool
    error_message: str | None = None


def default_output_path(*, captured_at: datetime) -> Path:
    """Return the default timestamped snapshot path under data/."""
    stamp = captured_at.strftime("%Y%m%d-%H%M%S")
    return Path(f"data/ig_snapshot-{stamp}.json")


def known_shortcodes(*, cache_manager: CacheManager) -> set[str]:
    """Return shortcodes already present in the post cache."""
    shortcodes: set[str] = set()
    for path in cache_manager.posts_dir.glob("*.json"):
        try:
            media = Media.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("Skipping unreadable cache file %s", path.name)
            continue
        if media.code:
            shortcodes.add(str(media.code))
    return shortcodes


def media_type_label(media: Media) -> str:
    """Map instagrapi media_type integers to IGbulkDL labels."""
    return _MEDIA_TYPE_LABELS.get(int(media.media_type), "unknown")


def title_for(media: Media) -> str | None:
    """Return an IGbulkDL-style title when Instagram does not supply one."""
    if media.title:
        return str(media.title)
    user = media.user
    author = user.username if user and user.username else None
    label = media_type_label(media)
    if author and label == "video":
        return f"Video by {author}"
    if author and label == "carousel":
        return f"Post by {author}"
    return None


def media_to_item(*, media: Media, captured_at: datetime) -> dict[str, object]:
    """Serialize one Media object into an IGbulkDL food.json item."""
    shortcode = str(media.code)
    user = media.user
    author = str(user.username) if user and user.username else ""
    username = str(user.pk) if user and user.pk is not None else str(media.pk)
    item: dict[str, object] = {
        "url": f"https://www.instagram.com/p/{shortcode}/",
        "shortcode": shortcode,
        "username": username,
        "author": author,
        "title": title_for(media),
        "caption": media.caption_text or None,
        "media_type": media_type_label(media),
        "status": "dry_run",
        "timestamp": captured_at.isoformat(),
    }
    return item


def build_summary(
    *,
    items: Sequence[dict[str, object]],
    captured_at: datetime,
) -> dict[str, object]:
    """Build the food.json summary block for a snapshot."""
    dry_run = sum(1 for item in items if item.get("status") == "dry_run")
    ok = sum(1 for item in items if item.get("status") == "ok")
    return {
        "total_in_file": len(items),
        "processed": len(items),
        "ok": ok,
        "failed": 0,
        "dry_run": dry_run,
        "skipped_auto": 0,
        "last_updated": captured_at.isoformat(),
    }


def collect_saved_posts(
    *,
    extractor: InstagramExtractor,
    collection_id: str,
    incremental: bool,
) -> SnapshotResult:
    """Page through a saved collection and return IGbulkDL-shaped items."""
    cache_manager = extractor.cache_manager
    known_at_start = known_shortcodes(cache_manager=cache_manager)
    captured_at = datetime.now(tz=UTC)
    items: list[dict[str, object]] = []
    fetched = 0
    new_since_last = 0
    last_media_pk = 0
    partial = False
    error_message: str | None = None

    while True:
        try:
            batch = extractor.fetch_collection_page(
                collection_id=collection_id,
                limit=_BATCH_SIZE,
                last_media_pk=last_media_pk,
            )
        except InstagramFetchError as exc:
            partial = True
            error_message = str(exc)
            logger.exception("Stopping early after API failure")
            break

        if not batch:
            break

        stop_after_batch = False
        batch_to_cache: list[Media] = []
        for media in batch:
            shortcode = str(media.code)
            if incremental and shortcode in known_at_start:
                stop_after_batch = True
                break

            fetched += 1
            if shortcode not in known_at_start:
                new_since_last += 1

            item = media_to_item(media=media, captured_at=captured_at)
            items.append(item)
            batch_to_cache.append(media)
            known_at_start.add(shortcode)

        if batch_to_cache:
            cache_manager.save_collection(
                collection_id=collection_id,
                posts=batch_to_cache,
            )

        if stop_after_batch:
            break

        if len(batch) < _BATCH_SIZE:
            break

        last_media_pk = int(batch[-1].pk)

    return SnapshotResult(
        items=tuple(items),
        fetched=fetched,
        new_since_last=new_since_last,
        partial=partial,
        error_message=error_message,
    )


def write_snapshot(
    *,
    output_path: Path,
    items: Sequence[dict[str, object]],
    captured_at: datetime,
) -> None:
    """Atomically write a food.json-shaped snapshot file."""
    payload = {
        "items": list(items),
        "summary": build_summary(items=items, captured_at=captured_at),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(output_path)
