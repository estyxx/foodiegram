import logging
import re
import secrets
import string
from typing import TYPE_CHECKING

from dispensa.domain.enums import RecipeSource
from dispensa.domain.models import ExtractedRecipe, Recipe

if TYPE_CHECKING:
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


def build_custom_recipe(
    draft: dict[str, object],
    *,
    recipes: RecipeRepository,
) -> Recipe:
    """Map a hand-authored draft into a manual Recipe, ready to save.

    The draft is shaped like the OpenAI extractor's output (see ExtractedRecipe)
    plus an optional inspired_by list of recipe codes. Fields the extractor
    always fills but a hand-drafted recipe often skips default to empty/unknown
    rather than being required.
    """
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


def save_custom_recipe(
    draft: dict[str, object],
    *,
    recipes: RecipeRepository,
) -> Recipe:
    """Build a manual Recipe from a draft and persist it, returning the saved recipe."""
    recipe = build_custom_recipe(draft, recipes=recipes)
    recipes.save(recipe)
    return recipe
