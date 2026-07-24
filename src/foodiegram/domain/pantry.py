import re
from datetime import date
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict

from foodiegram.domain.synonyms import expand_term

if TYPE_CHECKING:
    from collections.abc import Sequence


class PantryItem(BaseModel):
    """One thing the kitchen already has, matched by lowercase name."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Storage identity; None until persisted. Matching never uses it.
    id: int | None = None
    name: str
    kind: Literal["staple", "fresh"]
    expires: date | None = None


class KitchenMatch(BaseModel):
    """Ingredient lines split into what's on hand and what's still needed."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    have: list[str]
    missing: list[str]


def _line_has(line_lower: str, terms: frozenset[str]) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", line_lower) for term in terms)


def kitchen_match(
    ingredients: Sequence[str],
    pantry: Sequence[PantryItem],
) -> KitchenMatch:
    """Split ingredient lines into have/missing by naive pantry matching.

    A line counts as 'have' when any pantry name (synonym-expanded, both
    languages) appears as a word-boundary substring of the lowercased line.
    """
    terms = frozenset(term.lower() for item in pantry for term in expand_term(item.name))

    have: list[str] = []
    missing: list[str] = []
    for line in ingredients:
        if terms and _line_has(line.lower(), terms):
            have.append(line)
        else:
            missing.append(line)
    return KitchenMatch(have=have, missing=missing)
