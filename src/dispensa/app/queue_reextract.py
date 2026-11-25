import logging
from typing import TYPE_CHECKING, Protocol

from dispensa.ai.batch import MODEL, PROMPT_VERSION
from dispensa.app.queue_import import waiting_recipe
from dispensa.domain.editing import promote
from dispensa.domain.enums import PendingStatus
from dispensa.domain.errors import PendingLinkNotFoundError
from dispensa.domain.models import ExtractedRecipe, Extraction

if TYPE_CHECKING:
    from datetime import datetime

    from dispensa.domain.pending import PendingLink
    from dispensa.storage.extractions_db import ExtractionRepository
    from dispensa.storage.pending_db import PendingLinkRepository
    from dispensa.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)


class RecipeExtractor(Protocol):
    """Extracts one recipe from a caption, now (ai.repair.extract_recipe)."""

    def __call__(self, caption: str, /) -> ExtractedRecipe:
        """Return the extracted recipe; raise ExtractionError on failure."""
        ...


def reextract_queued(
    *,
    code: str,
    caption: str,
    now: datetime,
    pending: PendingLinkRepository,
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
    extract: RecipeExtractor,
) -> PendingLink:
    """Extract a queued link's recipe now, from caption, and save it.

    caption is the text to extract from: the post's caption, or the owner's own
    notes when the recipe lives in the comments or on a website. It replaces the
    stored caption on the link and the recipe. The result is added to the
    extraction history (kind "repair") and merged into the recipe, so a field the
    owner edited by hand keeps the owner's value. Works for a link already
    imported and for one still waiting for a batch. Raises ValueError for an empty
    caption and ExtractionError when the AI call fails, both before anything is
    saved.
    """
    link = pending.get(code)
    if link is None:
        msg = f"No queued link {code!r}"
        raise PendingLinkNotFoundError(msg)
    text = caption.strip()
    if not text:
        msg = "There is nothing to extract from: the caption is empty"
        raise ValueError(msg)

    extracted = extract(text)

    pending.set_caption(code, text)
    current = recipes.get(code) or waiting_recipe(link)
    # caption is protected from promote(), so the new text is set explicitly:
    # the recipe keeps the text it was extracted from.
    base = current.model_copy(update={"caption": text})
    extraction = Extraction(
        id=None,
        recipe_code=code,
        prompt_version=PROMPT_VERSION,
        model=MODEL,
        batch_id=None,
        kind="repair",
        extracted_at=now,
        payload=extracted,
    )
    # The recipe row before the extraction row: extractions.recipe_code is a
    # foreign key to recipes.code.
    recipes.save(promote(base, extraction))
    extractions.add(extraction)
    updated = pending.mark(code, PendingStatus.IMPORTED, imported_at=now)
    logger.info("Re-extracted %s from %d characters", code, len(text))
    return updated or link
