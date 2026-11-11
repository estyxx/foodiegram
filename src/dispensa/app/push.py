import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from dispensa.domain.editing import apply_push
from dispensa.domain.enums import RecipeSource

if TYPE_CHECKING:
    from dispensa.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)


class PushReport(BaseModel):
    """Outcome of a local → target recipe push."""

    model_config = ConfigDict(frozen=True)

    inserted: list[str]
    updated: list[str]
    unchanged: int
    target_only_kept: int
    dry_run: bool


def push_recipes(
    *,
    source: RecipeRepository,
    target: RecipeRepository,
    dry_run: bool,
) -> PushReport:
    """Insert new Instagram recipes and merge extraction updates into the target.

    Only Instagram recipes move. One the target lacks is inserted; one present on
    both has source's extraction fields overlaid except the target's edited_fields
    (D35). Manual recipes and every recipe only on the target are left untouched,
    and nothing is deleted. Reads only recipes — never plans, pantry or targets.
    """
    source_recipes = [
        recipe for recipe in source.list_all() if recipe.source == RecipeSource.INSTAGRAM
    ]
    target_by_code = {recipe.code: recipe for recipe in target.list_all()}
    source_codes = {recipe.code for recipe in source_recipes}

    inserted: list[str] = []
    updated: list[str] = []
    unchanged = 0
    for src in source_recipes:
        tgt = target_by_code.get(src.code)
        if tgt is None:
            if not dry_run:
                target.save(src)
            inserted.append(src.code)
        elif tgt.source != RecipeSource.INSTAGRAM:
            # The target owns a manual recipe at this code; never overwrite it.
            unchanged += 1
        else:
            merged = apply_push(tgt, src)
            if merged == tgt:
                unchanged += 1
            else:
                if not dry_run:
                    target.save(merged)
                updated.append(src.code)

    target_only_kept = sum(1 for code in target_by_code if code not in source_codes)
    report = PushReport(
        inserted=inserted,
        updated=updated,
        unchanged=unchanged,
        target_only_kept=target_only_kept,
        dry_run=dry_run,
    )
    logger.info(
        "push (%s): inserted=%d updated=%d unchanged=%d target_only_kept=%d",
        "dry-run" if dry_run else "applied",
        len(inserted),
        len(updated),
        unchanged,
        target_only_kept,
    )
    return report
