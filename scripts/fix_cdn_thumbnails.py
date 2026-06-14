import logging
import time

import cloudinary
import cloudinary.uploader

from foodiegram.repository import RecipeRepository
from foodiegram.settings import Settings

# --- Inputs / constants ---
CDN_PREFIX = "https://scontent-man2-1.cdninstagram."
INSTAGRAM_MEDIA_URL = "https://www.instagram.com/p/{code}/media/?size=l"
CLOUDINARY_FOLDER = "foodiegram"
UPLOAD_DELAY_SECONDS = 0.3

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Fix expired CDN thumbnail URLs and re-upload to Cloudinary."""
    settings = Settings()

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )

    repo = RecipeRepository(settings.data_dir)
    recipes = repo.list_all()

    affected = [
        r
        for r in recipes
        if r.thumbnail_url is not None and r.thumbnail_url.startswith(CDN_PREFIX)
    ]

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
            result: dict[str, object] = cloudinary.uploader.upload(
                stable_url,
                public_id=recipe.code,
                folder=CLOUDINARY_FOLDER,
                overwrite=True,
                resource_type="image",
            )
            cloudinary_url = str(result["secure_url"])
        except Exception as exc:  # noqa: BLE001  # reason: cloudinary SDK raises heterogeneous errors
            logger.warning("Cloudinary upload failed for %s: %s", recipe.code, exc)
            errors += 1
            continue

        updated = recipe.model_copy(
            update={
                "thumbnail_url": stable_url,
                "cloudinary_url": cloudinary_url,
            },
        )
        repo.save(updated)
        logger.info("Saved %s  cloudinary_url=%s", recipe.code, cloudinary_url)
        fixed += 1
        time.sleep(UPLOAD_DELAY_SECONDS)

    logger.info("Done — fixed %d, errors %d.", fixed, errors)


if __name__ == "__main__":
    main()
