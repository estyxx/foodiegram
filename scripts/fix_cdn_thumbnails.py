import logging
import time
from typing import TYPE_CHECKING

from foodiegram.domain.errors import ImageUploadError
from foodiegram.images import configure, is_expired_cdn_url, upload_thumbnail
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.recipes_db import RecipeRepository

if TYPE_CHECKING:
    from foodiegram.domain.models import Recipe

# --- Inputs / constants ---
INSTAGRAM_MEDIA_URL = "https://www.instagram.com/p/{code}/media/?size=l"
UPLOAD_DELAY_SECONDS = 0.3

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def is_broken(recipe: Recipe) -> bool:
    """Return True when the recipe's thumbnail is an expired Instagram CDN URL."""
    return recipe.thumbnail_url is not None and is_expired_cdn_url(recipe.thumbnail_url)


def with_uploaded(recipe: Recipe, *, stable_url: str, secure_url: str) -> Recipe:
    """Return a copy with the stable source thumbnail and durable Cloudinary URL."""
    return recipe.model_copy(
        update={
            "thumbnail_url": stable_url,
            "cloudinary_url": secure_url,
        },
    )


def main() -> None:
    """Fix expired CDN thumbnail URLs and re-upload to Cloudinary."""
    settings = Settings()
    configure(config=settings.require_cloudinary())

    engine = create_db_engine(settings.database_url)
    init_db(engine)
    repo = RecipeRepository(engine)
    recipes = repo.list_all()

    affected = [recipe for recipe in recipes if is_broken(recipe)]

    if not affected:
        logger.info("No recipes with CDN thumbnail URLs found.")
        return

    logger.info("Found %d recipe(s) with expired CDN thumbnail URLs.", len(affected))

    fixed = 0
    errors = 0

    for recipe in affected:
        stable_url = INSTAGRAM_MEDIA_URL.format(code=recipe.code)
        logger.info("Fixing %s  %s -> %s", recipe.code, recipe.thumbnail_url, stable_url)

        try:
            result = upload_thumbnail(
                shortcode=recipe.code,
                source_url_or_path=stable_url,
                overwrite=True,
            )
        except ImageUploadError as exc:
            logger.warning("Cloudinary upload failed for %s: %s", recipe.code, exc)
            errors += 1
            continue

        repo.save(
            with_uploaded(recipe, stable_url=stable_url, secure_url=result.secure_url),
        )
        logger.info("Saved %s  cloudinary_url=%s", recipe.code, result.secure_url)
        fixed += 1
        time.sleep(UPLOAD_DELAY_SECONDS)

    logger.info("Done — fixed %d, errors %d.", fixed, errors)


if __name__ == "__main__":
    main()
