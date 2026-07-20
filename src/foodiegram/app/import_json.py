import json
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, ValidationError

from foodiegram.domain.models import Recipe

if TYPE_CHECKING:
    from pathlib import Path

    from foodiegram.storage.recipes_db import RecipeRepository
    from foodiegram.storage.user_state_db import UserStateRepository

# Legacy per-recipe keys that now live in user_state; migrated on import.
_LEGACY_FAVORITE_KEY = "is_favorite"
_LEGACY_NOTES_KEY = "user_notes"

logger = logging.getLogger(__name__)


class ImportStats(BaseModel):
    """Outcome counts of a JSON-into-database import run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    imported: int = 0
    favorites: int = 0
    notes: int = 0
    errors: int = 0


def import_recipes(
    *,
    data_dir: Path,
    recipes: RecipeRepository,
    user_state: UserStateRepository,
) -> ImportStats:
    """Load every recipe JSON file in data_dir into the database.

    Legacy is_favorite/user_notes keys are migrated into user_state, then
    stripped before the Recipe validates.
    """
    imported = favorites = notes = errors = 0

    for path in sorted(data_dir.glob("*.json")):
        try:
            raw: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
            is_favorite = bool(raw.pop(_LEGACY_FAVORITE_KEY, False))
            user_notes = raw.pop(_LEGACY_NOTES_KEY, None)
            recipe = Recipe.model_validate(raw)
        except (json.JSONDecodeError, ValueError, ValidationError):
            logger.exception("Failed to import %s", path.name)
            errors += 1
            continue

        recipes.save(recipe)
        imported += 1

        if is_favorite:
            user_state.set_favorite(recipe.code, is_favorite=True)
            favorites += 1
        if user_notes is not None:
            user_state.set_notes(recipe.code, notes=str(user_notes))
            notes += 1

    return ImportStats(
        imported=imported,
        favorites=favorites,
        notes=notes,
        errors=errors,
    )
