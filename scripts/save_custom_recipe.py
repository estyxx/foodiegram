"""Save a hand-authored (or Instagram-riff) custom recipe.

Thin CLI wrapper over dispensa.app.save_custom_recipe. Reads a draft JSON
shaped like the OpenAI extractor's output (see ExtractedRecipe) plus an
optional inspired_by list of recipe codes, and saves it as a source=manual
recipe under a generated m-{slug}-{4 random base32} code (D11).

Run via:
uv run scripts/save_custom_recipe.py draft.json [--dry-run]
"""

import argparse
import json
import logging
from pathlib import Path

from pydantic import ValidationError

from dispensa.app.save_custom_recipe import build_custom_recipe, save_custom_recipe
from dispensa.settings import Settings
from dispensa.storage.db import create_db_engine, init_db
from dispensa.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)


def main() -> None:
    """Parse CLI args, build a manual Recipe from a draft JSON, and save it."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Save a hand-authored custom recipe from a draft JSON file.",
    )
    parser.add_argument("draft", type=Path, help="Path to the draft JSON file")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the recipe without saving it",
    )
    args = parser.parse_args()

    settings = Settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    recipes = RecipeRepository(engine)

    try:
        raw_draft = json.loads(args.draft.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        msg = f"Could not read {args.draft}: {exc}"
        raise SystemExit(msg) from exc

    try:
        if args.dry_run:
            recipe = build_custom_recipe(raw_draft, recipes=recipes)
        else:
            recipe = save_custom_recipe(raw_draft, recipes=recipes)
    except (ValidationError, TypeError) as exc:
        msg = f"Draft did not validate: {exc}"
        raise SystemExit(msg) from exc

    categories = [c.category.value for c in recipe.mediterranean_categories]
    verb = "Would save" if args.dry_run else "Saved"
    logger.info("%s %s: %s", verb, recipe.code, recipe.title)
    logger.info("  categories: %s", categories)
    logger.info("  inspired_by: %s", recipe.inspired_by)


if __name__ == "__main__":
    main()
