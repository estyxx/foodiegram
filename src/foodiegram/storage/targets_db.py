from typing import TYPE_CHECKING

from sqlmodel import select

from foodiegram.domain.planning import CategoryTarget
from foodiegram.storage._tables import TargetRow
from foodiegram.storage.db import get_session

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Engine


def _to_target(row: TargetRow) -> CategoryTarget:
    """Map a target row to the domain model, reviving the category enum."""
    return CategoryTarget.model_validate(
        {
            "category": row.category,
            "min_servings": row.min_servings,
            "max_servings": row.max_servings,
        },
    )


class TargetRepository:
    """Store for the weekly per-category serving targets."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def list_all(self) -> list[CategoryTarget]:
        """Return every target, ordered by category."""
        with get_session(self._engine) as session:
            rows = session.exec(select(TargetRow).order_by(TargetRow.category)).all()
            return [_to_target(row) for row in rows]

    def set_all(self, targets: Sequence[CategoryTarget]) -> list[CategoryTarget]:
        """Upsert each target by category and return the full set afterwards."""
        with get_session(self._engine) as session:
            for target in targets:
                row = session.get(TargetRow, target.category.value)
                if row is None:
                    row = TargetRow(
                        category=target.category.value,
                        min_servings=target.min_servings,
                        max_servings=target.max_servings,
                    )
                else:
                    row.min_servings = target.min_servings
                    row.max_servings = target.max_servings
                session.add(row)
            session.commit()
        return self.list_all()
