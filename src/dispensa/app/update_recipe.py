import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from dispensa.domain.editing import apply_user_edit
from dispensa.domain.errors import RecipeNotFoundError
from dispensa.domain.models import Recipe

if TYPE_CHECKING:
    from dispensa.storage.recipes_db import RecipeRepository
    from dispensa.storage.user_state_db import UserStateRepository

logger = logging.getLogger(__name__)


class RecipeEdit(BaseModel):
    """A partial user edit; only the fields explicitly set are applied.

    base_servings is a Recipe field and becomes user-owned (edited_fields);
    is_favorite and user_notes are per-user app state kept in user_state.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    base_servings: int | None = None
    is_favorite: bool | None = None
    user_notes: str | None = None


def update_recipe(
    code: str,
    *,
    edit: RecipeEdit,
    recipes: RecipeRepository,
    user_state: UserStateRepository,
) -> Recipe:
    """Apply edit to the recipe and its user state; return the stored recipe.

    Raises RecipeNotFoundError for an unknown code, before anything is written.
    """
    recipe = recipes.get(code)
    if recipe is None:
        msg = f"Recipe {code!r} not found"
        raise RecipeNotFoundError(msg)

    recipe_changes = {
        field: getattr(edit, field)
        for field in edit.model_fields_set
        if field in Recipe.model_fields
    }
    if recipe_changes:
        recipe = apply_user_edit(recipe, recipe_changes)
        recipes.save(recipe)
        logger.info("Edited %s: %s", code, sorted(recipe_changes))

    if "is_favorite" in edit.model_fields_set and edit.is_favorite is not None:
        user_state.set_favorite(code, is_favorite=edit.is_favorite)
    if "user_notes" in edit.model_fields_set:
        user_state.set_notes(code, notes=edit.user_notes)
    return recipe
