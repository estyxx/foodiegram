from typing import TYPE_CHECKING

from dispensa.domain.models import Extraction, Recipe

if TYPE_CHECKING:
    from collections.abc import Mapping

# Fields promote() must never touch: identity, media, and editing bookkeeping.
PROTECTED_FIELDS: frozenset[str] = frozenset(
    {
        "code",
        "source",
        "pk",
        "post_url",
        "caption",
        "cloudinary_url",
        "thumbnail_url",
        "edited_fields",
        "archived",
    },
)

# Every field Recipe.from_extracted produces from an ExtractedRecipe. Provenance
# stamps (prompt_version / model_used / extracted_at) are applied separately.
EXTRACTION_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "ingredients",
        "instructions",
        "summary",
        "meal_type",
        "dish_type",
        "cuisine_type",
        "difficulty",
        "course",
        "mediterranean_categories",
        "proteins",
        "vegetables",
        "grains_starches",
        "herbs_spices",
        "cooking_methods",
        "equipment",
        "prep_time",
        "cook_time",
        "total_time",
        "time_is_estimated",
        "servings",
        "base_servings",
        "temperature",
        "texture",
        "flavor_profile",
        "dietary_tags",
        "health_tags",
        "season",
        "occasion",
        "skill_level",
        "style_tags",
        "prep_style",
        "is_recipe",
        "confidence",
    },
)


def promote(current: Recipe, extraction: Extraction) -> Recipe:
    """Apply an extraction to a recipe, preserving user-edited fields."""
    mapped = Recipe.from_extracted(
        code=current.code,
        pk=current.pk,
        caption=current.caption,
        extracted=extraction.payload,
        model_used=extraction.model,
    )
    candidate = mapped.recipe

    frozen = current.edited_fields | PROTECTED_FIELDS
    update: dict[str, object] = {
        field: getattr(candidate, field)
        for field in EXTRACTION_FIELDS
        if field not in frozen
    }
    update["prompt_version"] = extraction.prompt_version
    update["model_used"] = extraction.model
    update["extracted_at"] = extraction.extracted_at

    return current.model_copy(update=update)


def apply_user_edit(recipe: Recipe, changes: Mapping[str, object]) -> Recipe:
    """Apply hand edits to recipe fields and record each one in edited_fields.

    Recording the field is what makes it user-owned: promote() never overwrites
    a field in edited_fields. Keys that are not Recipe fields are rejected.
    """
    unknown = sorted(set(changes) - set(Recipe.model_fields))
    if unknown:
        msg = f"Not recipe fields: {', '.join(unknown)}"
        raise ValueError(msg)
    if not changes:
        return recipe
    return recipe.model_copy(
        update={
            **changes,
            "edited_fields": recipe.edited_fields | frozenset(changes),
        },
    )
