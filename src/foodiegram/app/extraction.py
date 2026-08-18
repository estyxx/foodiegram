import json
import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from foodiegram.ai.batch import (
    PROMPT_VERSION,
    create_batch,
    fetch_batch_output,
    result_to_extraction,
    smoke_extract,
    submitted_codes,
    write_batch_input,
)
from foodiegram.domain.errors import ExtractionError

if TYPE_CHECKING:
    from datetime import datetime

    from foodiegram.domain.models import Recipe
    from foodiegram.settings import Settings
    from foodiegram.storage.extractions_db import ExtractionRepository
    from foodiegram.storage.recipes_db import RecipeRepository

MIN_CAPTION_LENGTH = 80

logger = logging.getLogger(__name__)


def _has_usable_caption(recipe: Recipe) -> bool:
    """Return True if the caption is long enough to be worth extracting."""
    return (
        recipe.caption is not None and len(recipe.caption.strip()) >= MIN_CAPTION_LENGTH
    )


def _eligible_for_submit(
    recipe: Recipe,
    *,
    excluded_codes: set[str],
    only_missing: bool,
) -> bool:
    """Return True if recipe should be submitted for extraction.

    only_missing skips recipes already extracted at the current PROMPT_VERSION or
    already sent in a prior submitted batch (applied or still in flight), so
    repeated calls advance through the backlog; only_missing=False (--all)
    re-submits every captioned, non-edited recipe regardless — use after a prompt
    or model change.
    """
    if recipe.edited_by_user:
        return False
    if not _has_usable_caption(recipe):
        return False
    return not (only_missing and recipe.code in excluded_codes)


def _extracted_codes(extractions: ExtractionRepository) -> set[str]:
    """Return the recipe codes already extracted at the current prompt version."""
    return {e.recipe_code for e in extractions.for_version(PROMPT_VERSION)}


def submit_batch(
    settings: Settings,
    *,
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
    only_missing: bool = True,
    limit: int | None = None,
    only_codes: set[str] | None = None,
    dry_run: bool = False,
) -> int:
    """Select recipes, build the batch input file, and create the OpenAI batch.

    With limit set, submit only the first `limit` eligible recipes — useful for a
    small, cheap test run before submitting the whole backlog. only_codes further
    restricts the selection to the given recipe codes. dry_run selects and logs
    but neither writes the input file nor creates the batch. Returns the number
    of recipes submitted (or that would be, under dry_run).
    """
    all_recipes = recipes.list_all()
    extracted_codes = _extracted_codes(extractions)
    already_submitted = submitted_codes()
    excluded_codes = extracted_codes | already_submitted
    to_submit = [
        r
        for r in all_recipes
        if _eligible_for_submit(
            r,
            excluded_codes=excluded_codes,
            only_missing=only_missing,
        )
        and (only_codes is None or r.code in only_codes)
    ]
    no_caption = [r for r in all_recipes if not _has_usable_caption(r)]

    eligible = len(to_submit)
    if limit is not None:
        to_submit = to_submit[:limit]

    mode = "only-missing" if only_missing else "all"
    logger.info("Total recipes: %d", len(all_recipes))
    logger.info("Already extracted at v%s: %d", PROMPT_VERSION, len(extracted_codes))
    logger.info("Already in a submitted batch: %d", len(already_submitted))
    logger.info("No caption: %d", len(no_caption))
    if limit is not None:
        logger.info(
            "Will submit: %d of %d eligible (limit=%d, mode=%s)",
            len(to_submit),
            eligible,
            limit,
            mode,
        )
    else:
        logger.info("Will submit: %d (mode=%s)", len(to_submit), mode)

    if not to_submit:
        logger.info("Nothing to submit.")
        return 0

    if dry_run:
        logger.info("Dry-run: not creating a batch.")
        return len(to_submit)

    create_batch(settings, input_path=write_batch_input(to_submit))
    return len(to_submit)


def apply_batch(
    settings: Settings,
    batch_id: str | None,
    *,
    extractions: ExtractionRepository,
    applied_at: datetime,
) -> None:
    """Download a completed batch and append its results as extraction rows.

    Writes extraction history only — never touches recipes. Run promote.py to
    merge these extractions into recipes (honouring user edits).
    """
    output = fetch_batch_output(settings, batch_id)
    if output is None:
        return

    added = 0
    errors = 0

    for raw_line in output.content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            extraction = result_to_extraction(
                line=line,
                batch_id=output.batch_id,
                extracted_at=applied_at,
            )
            extractions.add(extraction)
            added += 1
        except (
            KeyError,
            IndexError,
            TypeError,
            json.JSONDecodeError,
            ValidationError,
            ExtractionError,
        ):
            logger.exception("Failed to parse batch result line")
            errors += 1

    logger.info("Extractions added: %d  Errors: %d", added, errors)


def smoke_test(
    settings: Settings,
    *,
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
    limit: int,
) -> int:
    """Extract the first `limit` eligible captions synchronously; return passes."""
    excluded_codes = _extracted_codes(extractions) | submitted_codes()
    eligible = [
        r
        for r in recipes.list_all()
        if _eligible_for_submit(r, excluded_codes=excluded_codes, only_missing=True)
    ][:limit]
    return smoke_extract(settings, recipes=eligible)
