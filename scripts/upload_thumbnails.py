import logging
import time

import cloudinary
import cloudinary.uploader

from foodiegram.repository import RecipeRepository
from foodiegram.settings import Settings

# --- Inputs / constants ---
UPLOAD_DELAY_SECONDS = 0.3
CLOUDINARY_FOLDER = "foodiegram"

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Upload missing thumbnails to Cloudinary and update recipes with durable URLs."""
    settings = Settings()

    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
    )

    repo = RecipeRepository(settings.data_dir)
    recipes = repo.list_all()

    uploaded = 0
    skipped = 0
    errors = 0

    for recipe in recipes:
        if recipe.cloudinary_url is not None:
            skipped += 1
            continue

        if recipe.thumbnail_url is None:
            skipped += 1
            continue

        if recipe.caption:
            skipped += 1
            continue

        try:
            result: dict[str, object] = cloudinary.uploader.upload(
                recipe.thumbnail_url,
                public_id=recipe.code,
                folder=CLOUDINARY_FOLDER,
                overwrite=False,
                resource_type="image",
            )
            cloudinary_url = str(result["secure_url"])
        except Exception as exc:  # noqa: BLE001  # reason: cloudinary SDK raises heterogeneous errors
            logger.warning("Failed to upload %s: %s", recipe.code, exc)
            errors += 1
            continue

        updated = recipe.model_copy(update={"cloudinary_url": cloudinary_url})
        repo.save(updated)

        print(f"✓ {recipe.code}")
        uploaded += 1
        time.sleep(UPLOAD_DELAY_SECONDS)

    print(
        f"\nDone — uploaded {uploaded}, skipped {skipped}, errors {errors}.",
    )


if __name__ == "__main__":
    main()
