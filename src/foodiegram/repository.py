import logging
from pathlib import Path

from pydantic import ValidationError

from foodiegram.domain.enums import CuisineType, Difficulty, DishType, MealType
from foodiegram.domain.errors import StorageError
from foodiegram.domain.models import Recipe
from foodiegram.domain.synonyms import expand_term

logger = logging.getLogger(__name__)


class RecipeRepository:
    """JSON-backed store for Recipe objects, keyed by Instagram shortcode."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize repository, creating data_dir if absent."""
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, code: str) -> Path:
        """Return the JSON file path for a shortcode."""
        return self._data_dir / f"{code}.json"

    def get(self, code: str) -> Recipe | None:
        """Return the recipe for code, or None if it does not exist."""
        path = self._path(code)
        if not path.exists():
            return None
        try:
            return Recipe.model_validate_json(path.read_bytes())
        except (ValidationError, ValueError) as exc:
            msg = f"Corrupt recipe file {path}"
            raise StorageError(msg) from exc

    def save(self, recipe: Recipe) -> None:
        """Persist recipe to {code}.json, preserving user edits on re-extraction.

        Writes atomically via a sibling .tmp file and Path.replace.
        If the stored copy has edited_by_user=True, user_notes, is_favorite,
        and edited_by_user are kept from the stored version — AI re-extraction
        must never overwrite user edits.
        """
        path = self._path(recipe.code)

        if path.exists():
            try:
                existing = Recipe.model_validate_json(path.read_bytes())
                if existing.edited_by_user:
                    recipe = recipe.model_copy(
                        update={
                            "user_notes": existing.user_notes,
                            "is_favorite": existing.is_favorite,
                            "edited_by_user": existing.edited_by_user,
                        },
                    )
            except (ValidationError, ValueError):
                # Stale schema (pre-migration file) — no user edits can exist;
                # proceed and overwrite with the new format.
                logger.warning("Overwriting stale-schema file %s", path)

        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(recipe.model_dump_json(indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            msg = f"Failed to write recipe {recipe.code}"
            raise StorageError(msg) from exc

        logger.info("Saved recipe %s", recipe.code)

    def list_all(self) -> list[Recipe]:
        """Return all recipes found in data_dir, skipping unreadable files."""
        recipes: list[Recipe] = []
        for json_file in sorted(self._data_dir.glob("*.json")):
            try:
                recipe = self.get(json_file.stem)
            except StorageError:
                logger.exception("Skipping corrupt recipe file %s", json_file)
                continue
            if recipe is not None:
                recipes.append(recipe)
        return recipes

    def delete(self, code: str) -> bool:
        """Delete the recipe for code; return True if deleted, False if absent."""
        path = self._path(code)
        if not path.exists():
            return False
        try:
            path.unlink()
        except OSError as exc:
            msg = f"Failed to delete recipe {code}"
            raise StorageError(msg) from exc
        logger.info("Deleted recipe %s", code)
        return True

    def find(
        self,
        *,
        cuisine: CuisineType | None = None,
        meal_type: MealType | None = None,
        dish_type: DishType | None = None,
        difficulty: Difficulty | None = None,
        dietary_tags: list[str] | None = None,
        proteins: list[str] | None = None,
        q: str | None = None,
        is_favorite: bool | None = None,
    ) -> list[Recipe]:
        """Return recipes matching all non-None criteria.

        dietary_tags and proteins use ANY-match: a recipe passes if it contains
        at least one of the requested values (case-insensitive), with synonym
        expansion so e.g. "courgette" matches recipes tagged "zucchini".
        q is a case-insensitive substring match on title, caption, and
        ingredients, expanded via synonyms so "courgette" finds "zucchini" too.
        """
        results = self.list_all()

        if cuisine is not None:
            results = [r for r in results if r.cuisine_type == cuisine]
        if meal_type is not None:
            results = [r for r in results if r.meal_type == meal_type]
        if dish_type is not None:
            results = [r for r in results if r.dish_type == dish_type]
        if difficulty is not None:
            results = [r for r in results if r.difficulty == difficulty]
        if dietary_tags is not None:
            expanded_tags = {s.lower() for t in dietary_tags for s in expand_term(t)}
            results = [
                r for r in results if expanded_tags & {t.lower() for t in r.dietary_tags}
            ]
        if proteins is not None:
            expanded_proteins = {s.lower() for p in proteins for s in expand_term(p)}
            results = [
                r for r in results if expanded_proteins & {p.lower() for p in r.proteins}
            ]
        if q is not None:
            needles = {s.lower() for s in expand_term(q)}
            results = [
                r
                for r in results
                if any(needle in r.title.lower() for needle in needles)
                or any(
                    needle in ing.lower() for needle in needles for ing in r.ingredients
                )
                or (
                    r.caption is not None
                    and any(needle in r.caption.lower() for needle in needles)
                )
            ]
        if is_favorite is not None:
            results = [r for r in results if r.is_favorite == is_favorite]

        return results
