from datetime import datetime

from pydantic import BaseModel, ConfigDict

from dispensa.domain.enums import PendingStatus


class PendingLink(BaseModel):
    """A shared Instagram link waiting to become a recipe (the capture queue).

    The caption is read from the public post when the link is queued (D57),
    or pasted by hand when Instagram refuses; the thumbnail and batch id are
    filled as the item moves through extraction.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    url: str
    caption: str | None = None
    thumbnail_url: str | None = None
    status: PendingStatus = PendingStatus.NEW
    batch_id: str | None = None
    created_at: datetime
    # When it last became a recipe (import or re-extraction); None until then.
    imported_at: datetime | None = None
