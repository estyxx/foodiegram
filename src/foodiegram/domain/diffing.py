from pydantic import BaseModel, ConfigDict

from foodiegram.domain.editing import EXTRACTION_FIELDS, PROTECTED_FIELDS, promote
from foodiegram.domain.models import ExtractedRecipe, Extraction, Recipe

# Open tag lists whose order carries no meaning — compared as multisets. Ordered
# content (ingredients, instructions) is deliberately excluded: its order matters.
ORDER_INSENSITIVE_FIELDS: frozenset[str] = frozenset(
    {
        "proteins",
        "vegetables",
        "grains_starches",
        "herbs_spices",
        "cooking_methods",
        "equipment",
        "texture",
        "flavor_profile",
        "dietary_tags",
        "health_tags",
        "season",
        "occasion",
        "style_tags",
        "prep_style",
    },
)


class FieldDiff(BaseModel):
    """A single field whose value differs between two payloads."""

    model_config = ConfigDict(frozen=True)

    field: str
    old: object
    new: object


def _differs(*, field: str, old: object, new: object) -> bool:
    """Return True if old and new differ, ignoring order for tag-list fields."""
    if (
        field in ORDER_INSENSITIVE_FIELDS
        and isinstance(old, list)
        and isinstance(new, list)
    ):
        return sorted(old) != sorted(new)
    return old != new


def diff_payloads(a: ExtractedRecipe, b: ExtractedRecipe) -> list[FieldDiff]:
    """Diff two extraction payloads field by field.

    Tag lists compare order-insensitively; ingredients and instructions (and
    every scalar) compare order-sensitively.
    """
    diffs: list[FieldDiff] = []
    for field in ExtractedRecipe.model_fields:
        old = getattr(a, field)
        new = getattr(b, field)
        if _differs(field=field, old=old, new=new):
            diffs.append(FieldDiff(field=field, old=old, new=new))
    return diffs


def diff_against_recipe(recipe: Recipe, extraction: Extraction) -> list[FieldDiff]:
    """Return the fields promote() would change — the dry-run view.

    Excludes user-edited and protected fields, since promote() leaves those
    untouched.
    """
    promoted = promote(recipe, extraction)
    frozen = recipe.edited_fields | PROTECTED_FIELDS

    diffs: list[FieldDiff] = []
    for field in EXTRACTION_FIELDS:
        if field in frozen:
            continue
        old = getattr(recipe, field)
        new = getattr(promoted, field)
        if _differs(field=field, old=old, new=new):
            diffs.append(FieldDiff(field=field, old=old, new=new))
    return diffs
