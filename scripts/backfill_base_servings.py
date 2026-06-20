import logging
import re

from foodiegram.repository import RecipeRepository
from foodiegram.settings import Settings

# --- Inputs / constants ---
SERVINGS_DIGITS = re.compile(r"\d+")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def _parse_base_servings(servings: str) -> int | None:
    """Extract the first integer from a servings string, e.g. '3-4' → 3."""
    match = SERVINGS_DIGITS.search(servings)
    return int(match.group()) if match else None


def main() -> None:
    """Backfill base_servings for recipes where it is None but servings is set."""
    settings = Settings()

    repo = RecipeRepository(settings.data_dir)
    recipes = repo.list_all()

    updated = 0
    still_null = 0
    skipped = 0

    for recipe in recipes:
        if recipe.base_servings is not None:
            skipped += 1
            continue

        if recipe.servings is None:
            skipped += 1
            continue

        parsed = _parse_base_servings(recipe.servings)
        if parsed is None:
            logger.info(
                "No digit in servings for %s: %r",
                recipe.code,
                recipe.servings,
            )
            still_null += 1
            continue

        repo.save(recipe.model_copy(update={"base_servings": parsed}))
        logger.info(
            "Updated %s: servings=%r → base_servings=%d",
            recipe.code,
            recipe.servings,
            parsed,
        )
        updated += 1

    print(f"updated {updated}, still null {still_null}, skipped {skipped}")


if __name__ == "__main__":
    main()
