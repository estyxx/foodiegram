import logging
import time
from typing import TYPE_CHECKING

from foodiegram.domain.errors import ImageUploadError
from foodiegram.images import configure, upload_thumbnail
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.recipes_db import RecipeRepository

if TYPE_CHECKING:
    from foodiegram.domain.models import Recipe

# --- Inputs / constants ---
UPLOAD_DELAY_SECONDS = 0.3

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def upload_source(recipe: Recipe) -> str | None:
    """Return the thumbnail to upload, or None when the recipe should be skipped.

    Preserves the original filter: only captionless recipes that already have a
    source thumbnail but no durable Cloudinary URL are uploaded.
    """
    if recipe.cloudinary_url is not None:
        return None
    if recipe.caption:
        return None
    return recipe.thumbnail_url


def with_uploaded(recipe: Recipe, *, secure_url: str) -> Recipe:
    """Return a copy of recipe carrying the durable Cloudinary URL."""
    return recipe.model_copy(update={"cloudinary_url": secure_url})


def main() -> None:
    """Upload missing thumbnails to Cloudinary and update recipes with durable URLs."""
    settings = Settings()
    configure(config=settings.require_cloudinary())

    engine = create_db_engine(settings.database_url)
    init_db(engine)
    repo = RecipeRepository(engine)
    recipes = repo.list_all()

    uploaded = 0
    skipped = 0
    errors = 0

    for recipe in recipes:
        source_url = upload_source(recipe)
        if source_url is None:
            skipped += 1
            continue

        try:
            result = upload_thumbnail(
                shortcode=recipe.code,
                source_url_or_path=source_url,
                overwrite=False,
            )
        except ImageUploadError as exc:
            logger.warning("Failed to upload %s: %s", recipe.code, exc)
            errors += 1
            continue

        repo.save(with_uploaded(recipe, secure_url=result.secure_url))

        print(f"✓ {recipe.code}")
        uploaded += 1
        time.sleep(UPLOAD_DELAY_SECONDS)

    print(
        f"\nDone — uploaded {uploaded}, skipped {skipped}, errors {errors}.",
    )


if __name__ == "__main__":
    main()
