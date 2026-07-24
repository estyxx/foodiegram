from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from foodiegram.domain.diffing import FieldDiff, diff_payloads

if TYPE_CHECKING:
    from foodiegram.storage.extractions_db import ExtractionRepository


class RecipeVersionDiff(BaseModel):
    """How one recipe's extraction changed between two prompt versions."""

    model_config = ConfigDict(frozen=True)

    code: str
    diffs: tuple[FieldDiff, ...]


class VersionDiffReport(BaseModel):
    """Aggregate answer to 'I changed the prompt — what actually changed?'."""

    model_config = ConfigDict(frozen=True)

    from_version: str
    to_version: str
    compared: int
    changed: int
    field_counts: dict[str, int]
    changes: tuple[RecipeVersionDiff, ...]


def diff_versions(
    *,
    extractions: ExtractionRepository,
    from_version: str,
    to_version: str,
    field: str | None = None,
    code: str | None = None,
) -> VersionDiffReport:
    """Diff the latest extraction at from_version vs to_version, per recipe.

    Only recipes with an extraction at both versions are compared. field limits
    the diff to one field; code limits it to a single recipe.
    """
    old = extractions.latest_by_code(from_version)
    new = extractions.latest_by_code(to_version)
    codes = sorted(set(old) & set(new))
    if code is not None:
        codes = [c for c in codes if c == code]

    changes: list[RecipeVersionDiff] = []
    field_counts: dict[str, int] = {}

    for current in codes:
        diffs = diff_payloads(old[current].payload, new[current].payload)
        if field is not None:
            diffs = [diff for diff in diffs if diff.field == field]
        if not diffs:
            continue
        for diff in diffs:
            field_counts[diff.field] = field_counts.get(diff.field, 0) + 1
        changes.append(RecipeVersionDiff(code=current, diffs=tuple(diffs)))

    return VersionDiffReport(
        from_version=from_version,
        to_version=to_version,
        compared=len(codes),
        changed=len(changes),
        field_counts=field_counts,
        changes=tuple(changes),
    )
