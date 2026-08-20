import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from foodiegram.app.ingest import STABLE_MEDIA_URL, ThumbnailUploader
from foodiegram.domain.errors import ImageUploadError
from foodiegram.images import is_valid_image_ref

if TYPE_CHECKING:
    from foodiegram.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackfillReport:
    """Recipe codes whose durable Cloudinary image was fixed, or failed to upload."""

    fixed_codes: tuple[str, ...]
    failed_codes: tuple[str, ...]

    @property
    def fixed(self) -> int:
        """Count of recipes whose image was (or would be, under dry-run) uploaded."""
        return len(self.fixed_codes)

    @property
    def failed(self) -> int:
        """Count of recipes whose upload was attempted and failed."""
        return len(self.failed_codes)


def backfill_images(
    *,
    recipes: RecipeRepository,
    upload: ThumbnailUploader,
    dry_run: bool = False,
) -> BackfillReport:
    """Re-upload a durable image for every stored recipe missing or with a broken one.

    Unlike ingest_food_json, this scans every recipe already in the DB rather than
    one food.json batch — catches recipes whose image never got uploaded (or whose
    ref later broke) and have since fallen out of the current food.json export.
    A single recipe's upload failing (e.g. the Instagram post was since deleted)
    is logged and skipped rather than aborting the rest of the run.
    """
    to_fix = [r for r in recipes.list_all() if not is_valid_image_ref(r.cloudinary_url)]
    fixed: list[str] = []
    failed: list[str] = []
    for recipe in to_fix:
        if dry_run:
            fixed.append(recipe.code)
            continue
        source = STABLE_MEDIA_URL.format(code=recipe.code)
        try:
            uploaded = upload(shortcode=recipe.code, source_url_or_path=source)
        except ImageUploadError:
            logger.exception("Backfill upload failed for %s", recipe.code)
            failed.append(recipe.code)
            continue
        recipes.save(
            recipe.model_copy(
                update={"cloudinary_url": uploaded.secure_url, "thumbnail_url": source},
            ),
        )
        fixed.append(recipe.code)
    return BackfillReport(fixed_codes=tuple(fixed), failed_codes=tuple(failed))
