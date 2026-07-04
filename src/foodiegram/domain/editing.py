from foodiegram.domain.models import Extraction, Recipe

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
