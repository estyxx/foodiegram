import logging
from typing import TYPE_CHECKING

from dispensa.domain.editing import revert_field
from dispensa.domain.errors import ExtractionError, RecipeNotFoundError

if TYPE_CHECKING:
    from dispensa.domain.models import Recipe
    from dispensa.storage.extractions_db import ExtractionRepository
    from dispensa.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)


def revert_recipe_field(
    code: str,
    *,
    field: str,
    recipes: RecipeRepository,
    extractions: ExtractionRepository,
) -> Recipe:
    """Revert one user edit to its latest extracted value; save and return.

    Raises RecipeNotFoundError for an unknown code and ExtractionError when the
    recipe has no extraction to restore the field from. A field the user never
    edited is a no-op (returned unchanged, nothing written).
    """
    recipe = recipes.get(code)
    if recipe is None:
        msg = f"Recipe {code!r} not found"
        raise RecipeNotFoundError(msg)
    extraction = extractions.latest_for(code)
    if extraction is None:
        msg = f"Recipe {code!r} has no extraction to revert {field!r} to"
        raise ExtractionError(msg)
    reverted = revert_field(recipe, extraction, field)
    if reverted is not recipe:
        recipes.save(reverted)
        logger.info("Reverted %s field %s", code, field)
    return reverted
