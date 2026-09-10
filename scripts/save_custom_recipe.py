"""Save a hand-authored (or Instagram-riff) custom recipe.

Reads a draft JSON shaped like the OpenAI extractor's output (see
ExtractedRecipe) plus an optional inspired_by list of recipe codes, maps it
through the same Recipe.from_extracted mapping the batch pipeline uses, then
saves it with source=manual under a generated m-{slug}-{4 random base32}
code (D11). Fields the extractor always fills but a hand-drafted recipe
often skips (dish_type, proteins, texture, ...) default to empty/unknown
rather than being required — empty beats a fabricated guess.

Run via:
uv run scripts/save_custom_recipe.py draft.json [--dry-run]
"""

import argparse
import json
import logging
import re
import secrets
import string
from pathlib import Path

from pydantic import ValidationError

from dispensa.domain.enums import RecipeSource
from dispensa.domain.models import ExtractedRecipe, Recipe
from dispensa.settings import Settings
from dispensa.storage.db import create_db_engine, init_db
from dispensa.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)

_BASE32_ALPHABET = string.ascii_uppercase + "234567"
_SUFFIX_LEN = 4
_SLUG_MAX_LEN = 40
_SLUG_RE = re.compile(r"[^a-z0-9]+")

# ExtractedRecipe fields the LLM always fills but a hand-authored draft often
# won't bother with. Defaulted here rather than made optional on the model
# itself, since that model's shape must stay exactly what the batch pipeline
# produces.
_STRING_DEFAULTS = {
    "dish_type": "unknown",
    "meal_type": "unknown",
    "cuisine_type": "unknown",
    "difficulty": "unknown",
    "prep_time": "",
    "cook_time": "",
    "total_time": "",
    "servings": "",
    "temperature": "",
    "skill_level": "unknown",
}
_LIST_DEFAULTS: dict[str, list[str]] = {
    "proteins": [],
    "vegetables": [],
    "grains_starches": [],
    "herbs_spices": [],
    "cooking_methods": [],
    "equipment": [],
    "texture": [],
    "flavor_profile": [],
    "dietary_tags": [],
    "health_tags": [],
    "season": [],
    "occasion": [],
    "style_tags": [],
    "prep_style": [],
}


def _slugify(title: str) -> str:
    """Lowercase, hyphenate a title into a short slug for the manual code."""
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    return slug[:_SLUG_MAX_LEN] or "recipe"


def _random_suffix() -> str:
    """4 random base32 characters, matching D11's m-{slug}-{suffix} scheme."""
    return "".join(secrets.choice(_BASE32_ALPHABET) for _ in range(_SUFFIX_LEN))


def _generate_code(title: str, *, recipes: RecipeRepository) -> str:
    """Generate a unique m-{slug}-{4 random base32} code for a manual recipe."""
    slug = _slugify(title)
    while True:
        code = f"m-{slug}-{_random_suffix()}"
        if not recipes.exists(code):
            return code


def build_recipe(draft: dict[str, object], *, recipes: RecipeRepository) -> Recipe:
    """Map a hand-authored draft into a manual Recipe, ready to save."""
    raw = dict(draft)
    raw_inspired_by = raw.pop("inspired_by", [])
    if not isinstance(raw_inspired_by, list):
        msg = "inspired_by must be a list of recipe codes"
        raise TypeError(msg)
    inspired_by = [str(code) for code in raw_inspired_by]
    for key, default in {**_STRING_DEFAULTS, **_LIST_DEFAULTS}.items():
        raw.setdefault(key, default)
    raw.setdefault("is_recipe", True)
    raw.setdefault("confidence", 1.0)
    extracted = ExtractedRecipe.model_validate(raw)

    code = _generate_code(extracted.title, recipes=recipes)
    mapped = Recipe.from_extracted(code=code, pk=None, caption=None, extracted=extracted)
    if mapped.dropped_categories:
        logger.warning(
            "Dropped unknown categories for %s: %s",
            code,
            mapped.dropped_categories,
        )

    # CategoryServing.source distinguishes an LLM-assigned category from a
    # hand-set one; from_extracted always writes "llm", so override it here.
    manual_categories = [
        serving.model_copy(update={"source": "manual"})
        for serving in mapped.recipe.mediterranean_categories
    ]
    return mapped.recipe.model_copy(
        update={
            "source": RecipeSource.MANUAL,
            "post_url": None,
            "inspired_by": inspired_by,
            "mediterranean_categories": manual_categories,
        },
    )


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
        recipe = build_recipe(raw_draft, recipes=recipes)
    except (ValidationError, TypeError) as exc:
        msg = f"Draft did not validate: {exc}"
        raise SystemExit(msg) from exc

    categories = [c.category.value for c in recipe.mediterranean_categories]
    if args.dry_run:
        print(f"Would save {recipe.code}: {recipe.title}")
        print(f"  categories: {categories}")
        print(f"  inspired_by: {recipe.inspired_by}")
        return

    recipes.save(recipe)
    print(f"Saved {recipe.code}: {recipe.title}")
    print(f"  categories: {categories}")
    print(f"  inspired_by: {recipe.inspired_by}")


if __name__ == "__main__":
    main()
