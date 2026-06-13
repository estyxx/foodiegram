"""One-shot migration: re-key legacy recipe JSON by Instagram shortcode.

Reads the legacy per-recipe files (keyed by the corrupted `post_id`/`post_pk`),
re-keys them by the stable shortcode `code`, derives a clean string `pk` from that
code, coerces stray closed-set values, validates through the domain `Recipe`, and
writes one `{code}.json` per recipe to a fresh output directory.
"""

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from foodiegram.domain import CuisineType, Difficulty, DishType, MealType, Recipe

SOURCE_DIR = Path("data/recipes")
TARGET_DIR = Path("data/recipes_clean")

# Instagram shortcodes are URL-safe base64 of the media pk.
_SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
# Legacy keys that map to the model's `pk` (or are dropped entirely).
_DROPPED_KEYS = ("_metadata", "post_id", "post_pk")

logger = logging.getLogger(__name__)

E = TypeVar("E", bound=StrEnum)


@dataclass
class _Stats:
    """Running totals for a migration run."""

    processed: int = 0
    written: int = 0
    skipped: int = 0
    coerced: int = 0
    duplicates: int = 0


def _pk_from_code(code: str) -> str:
    """Decode an Instagram shortcode into its numeric media pk (as a string)."""
    pk = 0
    for char in code:
        pk = pk * 64 + _SHORTCODE_ALPHABET.index(char)
    return str(pk)


def _coerce_enum(raw: object, enum_cls: type[E], default: E, *, code: str) -> E:
    """Return the matching enum member, or `default` if the value is invalid."""
    if isinstance(raw, str):
        try:
            return enum_cls(raw)
        except ValueError:
            pass
    logger.warning(
        "%s: coercing invalid %s value %r -> %s",
        code,
        enum_cls.__name__,
        raw,
        default.value,
    )
    return default


def _to_recipe(raw: dict[str, object], stats: _Stats) -> Recipe | None:
    """Map one legacy recipe dict to a validated domain `Recipe`."""
    code = raw.get("code")
    if not isinstance(code, str) or not code:
        logger.warning("Skipping record with missing/invalid code: %r", raw.get("code"))
        return None

    fields = {key: value for key, value in raw.items() if key not in _DROPPED_KEYS}
    fields["pk"] = _pk_from_code(code)

    before = (
        fields.get("meal_type"),
        fields.get("dish_type"),
        fields.get("cuisine_type"),
        fields.get("difficulty"),
    )
    fields["meal_type"] = _coerce_enum(
        before[0],
        MealType,
        MealType.UNKNOWN,
        code=code,
    )
    fields["dish_type"] = _coerce_enum(
        before[1],
        DishType,
        DishType.UNKNOWN,
        code=code,
    )
    fields["cuisine_type"] = _coerce_enum(
        before[2],
        CuisineType,
        CuisineType.UNKNOWN,
        code=code,
    )
    fields["difficulty"] = _coerce_enum(
        before[3],
        Difficulty,
        Difficulty.UNKNOWN,
        code=code,
    )
    after = (
        fields["meal_type"],
        fields["dish_type"],
        fields["cuisine_type"],
        fields["difficulty"],
    )
    stats.coerced += sum(1 for old, new in zip(before, after, strict=True) if old != new)

    try:
        return Recipe.model_validate(fields)
    except ValidationError:
        logger.exception("%s: failed validation", code)
        return None


def migrate(source_dir: Path, target_dir: Path) -> _Stats:
    """Migrate every recipe file in `source_dir` into `target_dir`, keyed by code."""
    target_dir.mkdir(parents=True, exist_ok=True)
    stats = _Stats()
    seen: set[str] = set()

    for path in sorted(source_dir.glob("*.json")):
        stats.processed += 1
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("Could not read %s", path)
            stats.skipped += 1
            continue

        recipe = _to_recipe(raw, stats)
        if recipe is None:
            stats.skipped += 1
            continue

        if recipe.code in seen:
            logger.warning(
                "Duplicate code %s (from %s) — keeping first",
                recipe.code,
                path,
            )
            stats.duplicates += 1
            continue
        seen.add(recipe.code)

        out_path = target_dir / f"{recipe.code}.json"
        out_path.write_text(recipe.model_dump_json(indent=2), encoding="utf-8")
        stats.written += 1

    return stats


def main() -> None:
    """Run the migration and log a summary."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = migrate(SOURCE_DIR, TARGET_DIR)
    logger.info(
        "Done: %d processed, %d written, %d skipped, %d duplicates, %d fields coerced",
        stats.processed,
        stats.written,
        stats.skipped,
        stats.duplicates,
        stats.coerced,
    )


if __name__ == "__main__":
    main()
