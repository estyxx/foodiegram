from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from foodiegram.domain.diffing import FieldDiff, diff_against_recipe
from foodiegram.domain.editing import EXTRACTION_FIELDS, promote

if TYPE_CHECKING:
    from foodiegram.storage.extractions_db import ExtractionRepository
    from foodiegram.storage.recipes_db import RecipeRepository


class RecipePromotion(BaseModel):
    """The change promote() would apply (dry-run) or applied to one recipe."""

    model_config = ConfigDict(frozen=True)

    code: str
    diffs: tuple[FieldDiff, ...]
    skipped_fields: tuple[str, ...]


class PromotionReport(BaseModel):
    """Outcome of promoting one prompt version across the library."""

    model_config = ConfigDict(frozen=True)

    version: str
    dry_run: bool
    considered: int
    changed: int
    promoted: int
    missing_recipe: int
    changes: tuple[RecipePromotion, ...]

    @property
    def total_skipped_fields(self) -> int:
        """Total user-edited fields left untouched across all recipes."""
        return sum(len(change.skipped_fields) for change in self.changes)


def promote_version(
    *,
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
    version: str,
    batch_id: str | None = None,
    dry_run: bool = True,
) -> PromotionReport:
    """Promote the latest extraction at version into each recipe.

    Reports the fields promote() changes and the user-edited fields it preserves.
    With dry_run=False, promoted recipes are saved; user edits are never at risk.
    """
    latest = extractions.latest_by_code(version, batch_id=batch_id)
    recipe_by_code = {recipe.code: recipe for recipe in recipes.list_all()}

    changes: list[RecipePromotion] = []
    considered = 0
    promoted = 0
    missing = 0

    for code, extraction in latest.items():
        recipe = recipe_by_code.get(code)
        if recipe is None:
            missing += 1
            continue
        considered += 1

        diffs = diff_against_recipe(recipe, extraction)
        skipped = tuple(sorted(recipe.edited_fields & EXTRACTION_FIELDS))
        if not diffs and not skipped:
            continue

        if diffs and not dry_run:
            recipes.save(promote(recipe, extraction))
            promoted += 1

        changes.append(
            RecipePromotion(
                code=code,
                diffs=tuple(diffs),
                skipped_fields=skipped,
            ),
        )

    changed = sum(1 for change in changes if change.diffs)
    return PromotionReport(
        version=version,
        dry_run=dry_run,
        considered=considered,
        changed=changed,
        promoted=promoted,
        missing_recipe=missing,
        changes=tuple(changes),
    )
