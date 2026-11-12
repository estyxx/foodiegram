import json
import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from dispensa.ai.batch import fetch_batch_output, result_to_extraction
from dispensa.domain.editing import promote
from dispensa.domain.enums import BatchStatus, PendingStatus, RecipeSource
from dispensa.domain.errors import ExtractionError
from dispensa.domain.models import Recipe

if TYPE_CHECKING:
    from datetime import datetime

    from dispensa.domain.pending import PendingLink
    from dispensa.settings import Settings
    from dispensa.storage.batches_db import BatchRepository
    from dispensa.storage.extractions_db import ExtractionRepository
    from dispensa.storage.pending_db import PendingLinkRepository
    from dispensa.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)

_PARSE_ERRORS = (
    KeyError,
    IndexError,
    TypeError,
    json.JSONDecodeError,
    ValidationError,
    ExtractionError,
)


def _waiting_recipe(link: PendingLink) -> Recipe:
    """Build the empty Instagram recipe a finished extraction is promoted onto."""
    return Recipe(
        code=link.code,
        source=RecipeSource.INSTAGRAM,
        pk=None,
        post_url=link.url,
        caption=link.caption,
        thumbnail_url=link.thumbnail_url,
        title=None,
        ingredients=[],
        instructions=[],
    )


def import_finished_queue(
    settings: Settings,
    *,
    pending: PendingLinkRepository,
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
    batches: BatchRepository,
    now: datetime,
    batch_id: str | None = None,
) -> int:
    """Apply a finished batch, build the recipes, and mark the links imported.

    Reads the completed batch output, and for every result whose code is still an
    EXTRACTING queue link: appends the extraction (history), promotes it onto a
    fresh Instagram recipe, saves it, and marks the link IMPORTED. Returns the
    number imported; 0 when the batch is not ready. Idempotent — a second run
    skips links already imported, so no duplicate extraction is appended. A link
    that got no result stays EXTRACTING for a later import.
    """
    if batch_id is None:
        latest = batches.latest()
        batch_id = latest.batch_id if latest is not None else None
    output = fetch_batch_output(settings, batch_id)
    if output is None:
        return 0

    extracting = {
        link.code: link
        for link in pending.list_all()
        if link.status is PendingStatus.EXTRACTING
    }
    imported = 0
    for raw_line in output.content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        try:
            extraction = result_to_extraction(
                line=line,
                batch_id=output.batch_id,
                extracted_at=now,
            )
        except _PARSE_ERRORS:
            logger.exception("Queue import: bad batch line %r", line[:120])
            continue
        link = extracting.get(extraction.recipe_code)
        if link is None:
            continue
        # Save the recipe before the extraction row: extractions.recipe_code is a
        # foreign key to recipes.code.
        recipes.save(promote(_waiting_recipe(link), extraction))
        extractions.add(extraction)
        pending.mark(link.code, PendingStatus.IMPORTED)
        imported += 1

    batches.mark(output.batch_id, BatchStatus.APPLIED)
    logger.info("Queue import: imported %d recipe(s) from %s", imported, output.batch_id)
    return imported
