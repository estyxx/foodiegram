import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from foodiegram.domain.pantry import kitchen_match
from foodiegram.domain.synonyms import SYNONYM_GROUPS, canonical_term

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from foodiegram.domain.models import Recipe
    from foodiegram.domain.pantry import PantryItem
    from foodiegram.domain.planning import WeekPlan

_UNKNOWN_AISLE = "altro"

# Numbers only — the same shape the scaling widget uses (see CLAUDE.md).
_QUANTITY_RE = re.compile(r"\d+\.?\d*")

# Common measurement words dropped alongside the numbers so quantities collapse.
_UNITS = frozenset(
    {
        "g",
        "gr",
        "kg",
        "mg",
        "ml",
        "l",
        "cl",
        "dl",
        "tbsp",
        "tbs",
        "tsp",
        "cup",
        "cups",
        "oz",
        "lb",
        "lbs",
        "clove",
        "cloves",
        "spicchio",
        "spicchi",
        "cucchiaio",
        "cucchiai",
        "cucchiaino",
        "cucchiaini",
        "tazza",
        "tazze",
        "pinch",
        "slice",
        "slices",
    },
)

# Known ingredient terms, longest first so multi-word terms win the scan.
_KNOWN_TERMS: list[str] = sorted(
    {term.lower() for group in SYNONYM_GROUPS for term in group},
    key=len,
    reverse=True,
)


class ShoppingItem(BaseModel):
    """A needed ingredient under its canonical name, keeping the raw lines."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    raw_lines: list[str]


class AisleGroup(BaseModel):
    """Shopping items grouped by the supermarket aisle they belong to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    aisle: str
    items: list[ShoppingItem]


def _clean(line: str) -> str:
    stripped = _QUANTITY_RE.sub(" ", line.lower())
    tokens = [token for token in stripped.split() if token not in _UNITS]
    return " ".join(tokens).strip()


def _canonical_name(line: str) -> str:
    cleaned = _clean(line)
    for term in _KNOWN_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", cleaned):
            return canonical_term(term)
    return cleaned


def shopping_list(
    plan: WeekPlan,
    recipes: Mapping[str, Recipe],
    pantry: Sequence[PantryItem],
    aisles: Mapping[str, str],
) -> list[AisleGroup]:
    """Group the week's not-in-pantry ingredients into an aisle-sorted list.

    Missing lines are quantity-stripped, synonym-canonicalised and de-duplicated
    (raw lines kept as detail), then grouped via aisles; unknown maps to 'altro'.
    """
    by_name: dict[str, list[str]] = {}
    for meal in plan.meals:
        recipe = recipes.get(meal.recipe_code)
        if recipe is None:
            continue
        for line in kitchen_match(recipe.ingredients, pantry).missing:
            name = _canonical_name(line)
            if not name:
                continue
            raw_lines = by_name.setdefault(name, [])
            if line not in raw_lines:
                raw_lines.append(line)

    by_aisle: dict[str, list[ShoppingItem]] = {}
    for name in sorted(by_name):
        aisle = aisles.get(name, _UNKNOWN_AISLE)
        item = ShoppingItem(name=name, raw_lines=by_name[name])
        by_aisle.setdefault(aisle, []).append(item)

    return [AisleGroup(aisle=aisle, items=by_aisle[aisle]) for aisle in sorted(by_aisle)]
