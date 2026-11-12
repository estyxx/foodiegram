import logging
from typing import TYPE_CHECKING

from dispensa.ai.batch import PROMPT_VERSION, create_batch, write_batch_input
from dispensa.domain.batch import BatchRun
from dispensa.domain.enums import PendingStatus

if TYPE_CHECKING:
    from datetime import datetime

    from dispensa.domain.pending import PendingLink
    from dispensa.settings import Settings
    from dispensa.storage.batches_db import BatchRepository
    from dispensa.storage.pending_db import PendingLinkRepository

logger = logging.getLogger(__name__)


def _ready_for_extraction(
    links: list[PendingLink],
    *,
    already_submitted: set[str],
    only_codes: set[str] | None,
) -> list[PendingLink]:
    """Return ready, captioned links not already in a batch, respecting only_codes."""
    return [
        link
        for link in links
        if link.status is PendingStatus.READY
        and link.caption
        and link.code not in already_submitted
        and (only_codes is None or link.code in only_codes)
    ]


def launch_queue_extraction(
    settings: Settings,
    *,
    pending: PendingLinkRepository,
    batches: BatchRepository,
    now: datetime,
    only_codes: set[str] | None = None,
) -> int:
    """Submit a batch for the ready queue items and mark them extracting.

    Builds the batch input straight from the queued captions (no recipe row is
    created yet — that happens on import, when the batch finishes). Records the
    BatchRun so a disk-less process can find it later, and stamps each link
    EXTRACTING with the batch id. Returns the number of links submitted; 0 when
    nothing is ready. Links already in a submitted batch are skipped.
    """
    ready = _ready_for_extraction(
        pending.list_all(),
        already_submitted=batches.all_submitted_codes(),
        only_codes=only_codes,
    )
    if not ready:
        logger.info("Queue extraction: nothing ready to submit.")
        return 0

    batch_id = create_batch(settings, input_path=write_batch_input(ready))
    batches.record(
        BatchRun(
            batch_id=batch_id,
            prompt_version=PROMPT_VERSION,
            codes=tuple(link.code for link in ready),
            submitted_at=now,
        ),
    )
    for link in ready:
        pending.mark(link.code, PendingStatus.EXTRACTING, batch_id=batch_id)
    logger.info("Queue extraction: submitted %d link(s) as %s", len(ready), batch_id)
    return len(ready)
