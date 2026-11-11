from typing import TYPE_CHECKING

from dispensa.app.ingest import POST_URL, shortcode_from_url
from dispensa.domain.enums import PendingStatus
from dispensa.domain.errors import LinkAlreadyKnownError, PendingLinkNotFoundError
from dispensa.domain.pending import PendingLink

if TYPE_CHECKING:
    from datetime import datetime

    from dispensa.storage.pending_db import PendingLinkRepository
    from dispensa.storage.recipes_db import RecipeRepository


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
