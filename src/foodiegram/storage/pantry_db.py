from typing import TYPE_CHECKING

from sqlmodel import select

from foodiegram.domain.pantry import PantryItem
from foodiegram.storage._tables import PantryItemRow
from foodiegram.storage.db import get_session

if TYPE_CHECKING:
    from sqlalchemy import Engine


def _to_item(row: PantryItemRow) -> PantryItem:
    """Map a pantry row to the domain model."""
    return PantryItem.model_validate(
        {
            "id": row.id,
            "name": row.name,
            "kind": row.kind,
            "expires": row.expires,
        },
    )


class PantryRepository:
    """Store for pantry items the kitchen already has."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def list_all(self) -> list[PantryItem]:
        """Return every pantry item, ordered by name."""
        with get_session(self._engine) as session:
            rows = session.exec(select(PantryItemRow).order_by(PantryItemRow.name)).all()
            return [_to_item(row) for row in rows]

    def add(self, item: PantryItem) -> PantryItem:
        """Insert a pantry item and return it with its assigned id."""
        with get_session(self._engine) as session:
            row = PantryItemRow(name=item.name, kind=item.kind, expires=item.expires)
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_item(row)

    def delete(self, item_id: int) -> bool:
        """Delete the pantry item for item_id; return True if it existed."""
        with get_session(self._engine) as session:
            row = session.get(PantryItemRow, item_id)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
