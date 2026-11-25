import logging
import time
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, ConfigDict

from dispensa.app.ingest import POST_URL, shortcode_from_url
from dispensa.domain.enums import PendingStatus
from dispensa.domain.errors import LinkAlreadyKnownError, PendingLinkNotFoundError
from dispensa.domain.pending import PendingLink
from dispensa.instagram import CaptionFetch, CaptionOutcome

if TYPE_CHECKING:
    from datetime import datetime

    from dispensa.storage.pending_db import PendingLinkRepository
    from dispensa.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)


class CaptionFetcher(Protocol):
    """Reads a public post's caption from Instagram (fetch_public_caption)."""

    def __call__(self, code: str, /) -> CaptionFetch:
        """Return what one attempt to read the caption of code found."""
        ...


class QueuedLink(BaseModel):
    """A queued link, plus what the caption lookup found when one ran."""

    model_config = ConfigDict(frozen=True)

    link: PendingLink
    lookup: CaptionOutcome | None = None


def queue_link(
    *,
    url: str,
    now: datetime,
    pending: PendingLinkRepository,
    recipes: RecipeRepository,
) -> PendingLink:
    """Add a shared Instagram URL to the capture queue; idempotent per shortcode.

    Raises ValueError for a URL with no shortcode and LinkAlreadyKnownError when
    the post is already a recipe. A link already queued is returned unchanged.
    """
    code = shortcode_from_url(url)
    if code is None:
        msg = f"Not an Instagram post/reel URL: {url!r}"
        raise ValueError(msg)
    if recipes.exists(code):
        msg = f"{code} is already in the library"
        raise LinkAlreadyKnownError(msg)
    existing = pending.get(code)
    if existing is not None:
        return existing
    link = PendingLink(
        code=code,
        url=POST_URL.format(code=code),
        status=PendingStatus.NEW,
        created_at=now,
    )
    return pending.add(link)


def set_queued_caption(
    *,
    code: str,
    caption: str,
    pending: PendingLinkRepository,
) -> PendingLink:
    """Store the pasted caption on a queued link and mark it ready to extract."""
    link = pending.set_caption(code, caption)
    if link is None:
        msg = f"No queued link {code!r}"
        raise PendingLinkNotFoundError(msg)
    return link


def look_up_caption(
    *,
    code: str,
    pending: PendingLinkRepository,
    fetch: CaptionFetcher,
) -> QueuedLink:
    """Try to read a queued link's caption from Instagram and mark it ready.

    Best effort: when Instagram refuses, the link stays waiting for a pasted
    caption and the outcome says why. A caption already on the link (pasted or
    found earlier) is never replaced.
    """
    link = pending.get(code)
    if link is None:
        msg = f"No queued link {code!r}"
        raise PendingLinkNotFoundError(msg)
    if link.caption:
        return QueuedLink(link=link)
    started = time.monotonic()
    found = fetch(code)
    # One line per attempt is how the success rate from the server is judged.
    # The caption itself is never logged.
    logger.info(
        "Caption lookup %s: %s via %s in %.1fs %s",
        code,
        found.outcome.value,
        found.source or "-",
        time.monotonic() - started,
        found.detail,
    )
    if found.outcome is CaptionOutcome.FOUND and found.caption:
        updated = set_queued_caption(code=code, caption=found.caption, pending=pending)
        return QueuedLink(link=updated, lookup=found.outcome)
    return QueuedLink(link=link, lookup=found.outcome)
