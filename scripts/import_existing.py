"""One-shot migration: import index.json + extracted_recipes.json into RecipeRepository.

Run via: make import
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from foodiegram.domain.enums import CuisineType, Difficulty
from foodiegram.domain.errors import StorageError
from foodiegram.domain.models import ExtractedRecipe, Recipe
from foodiegram.repository import RecipeRepository

INDEX_DEFAULT = Path("cookstagram-data/data/index.json")
RICH_DEFAULT = Path("cookstagram-data/data/extracted_recipes.json")
OUT_DEFAULT = Path("data/recipes/")

# Keys present in extracted_recipes.json that are NOT part of ExtractedRecipe.
_RICH_EXTRA_KEYS = frozenset({"code", "post_id", "caption", "thumbnail_url"})

logger = logging.getLogger(__name__)


def _parse_code(post_url: str) -> str:
    """Parse the Instagram shortcode out of a /p/{code} URL."""
    parts = post_url.split("/p/")
    if len(parts) < 2 or not parts[1].strip("/"):
        msg = f"Cannot parse shortcode from URL: {post_url!r}"
        raise ValueError(msg)
    return parts[1].strip("/")


def _load_rich(rich_path: Path) -> dict[str, dict[str, Any]]:
    """Load extracted_recipes.json; return {} if the file does not exist."""
    if not rich_path.exists():
        logger.info("Rich data file not found (%s), proceeding without it", rich_path)
        return {}
    data: dict[str, Any] = json.loads(rich_path.read_text(encoding="utf-8"))
    return {item["code"]: item for item in data.get("recipes", [])}


def _to_cuisine(value: str) -> CuisineType:
    """Map a raw string to CuisineType, falling back to UNKNOWN."""
    try:
        return CuisineType(value.lower())
    except ValueError:
        return CuisineType.UNKNOWN


def _to_difficulty(value: str) -> Difficulty:
    """Map a raw string to Difficulty, falling back to UNKNOWN."""
    try:
        return Difficulty(value.lower())
    except ValueError:
        return Difficulty.UNKNOWN


def _build_shallow(post_pk: str, code: str, entry: dict[str, Any]) -> Recipe:
    """Build a Recipe from index.json fields only (no LLM extraction)."""
    return Recipe(
        code=code,
        pk=post_pk,
        post_url=entry.get("post_url", f"https://instagram.com/p/{code}/"),
        caption=None,
        title=entry.get("title", ""),
        ingredients=entry.get("ingredients", []),
        instructions=[],
        cuisine_type=_to_cuisine(entry.get("cuisine_type", "")),
        difficulty=_to_difficulty(entry.get("difficulty", "")),
        dietary_tags=entry.get("dietary_tags", []),
        cooking_methods=entry.get("cooking_methods", []),
    )


def _build_rich(post_pk: str, code: str, raw: dict[str, Any]) -> Recipe:
    """Build a Recipe from a full ExtractedRecipe payload.

    extracted_recipes.json carries post_id / caption / thumbnail_url alongside
    the ExtractedRecipe fields; strip them before validation, then attach the
    ones Recipe knows about.
    """
    caption: str | None = raw.get("caption") or None
    thumbnail_url: str | None = raw.get("thumbnail_url") or None
    extracted_data = {k: v for k, v in raw.items() if k not in _RICH_EXTRA_KEYS}
    extracted = ExtractedRecipe.model_validate(extracted_data)
    recipe = Recipe.from_extracted(
        code=code,
        pk=post_pk,
        caption=caption,
        extracted=extracted,
    )
    if thumbnail_url:
        recipe = recipe.model_copy(update={"thumbnail_url": thumbnail_url})
    return recipe


def main() -> None:
    """Run the import."""
    parser = argparse.ArgumentParser(
        description="Import existing recipe data into RecipeRepository.",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=INDEX_DEFAULT,
        metavar="PATH",
        help=f"index.json (default: {INDEX_DEFAULT})",
    )
    parser.add_argument(
        "--rich",
        type=Path,
        default=RICH_DEFAULT,
        metavar="PATH",
        help=f"extracted_recipes.json (default: {RICH_DEFAULT})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT_DEFAULT,
        metavar="DIR",
        help=f"Output recipe directory (default: {OUT_DEFAULT})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.index.exists():
        logger.error("index.json not found: %s", args.index)
        sys.exit(1)

    raw_index: dict[str, Any] = json.loads(args.index.read_text(encoding="utf-8"))
    rich = _load_rich(args.rich)
    repo = RecipeRepository(args.out)

    total = 0
    n_rich = 0
    n_shallow = 0
    skipped: list[tuple[str, str]] = []

    for post_pk, entry in raw_index["recipes"].items():
        total += 1
        post_url: str = entry.get("post_url", "")

        try:
            code = _parse_code(post_url)
        except ValueError as exc:
            skipped.append((post_pk, str(exc)))
            logger.warning("Skipping %s: %s", post_pk, exc)
            continue

        try:
            if code in rich:
                recipe = _build_rich(post_pk, code, rich[code])
                n_rich += 1
            else:
                recipe = _build_shallow(post_pk, code, entry)
                n_shallow += 1
            repo.save(recipe)
        except (StorageError, ValueError, KeyError) as exc:
            skipped.append((post_pk, str(exc)))
            logger.exception("Error processing post %s (code=%s)", post_pk, code)

    print("\nImport complete")
    print(f"  Total processed : {total}")
    print(f"  Fully extracted : {n_rich}")
    print(f"  Shallow import  : {n_shallow}")
    print(f"  Skipped / errors: {len(skipped)}")

    if skipped:
        print("\nSkipped entries:")
        for pk, reason in skipped:
            print(f"  {pk}: {reason}")


if __name__ == "__main__":
    main()
