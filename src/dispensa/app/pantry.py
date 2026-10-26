import logging
from typing import TYPE_CHECKING

from dispensa.domain.errors import PantryItemNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dispensa.domain.pantry import PantryItem
    from dispensa.storage.pantry_db import PantryRepository

logger = logging.getLogger(__name__)


def add_pantry_items(
    items: Sequence[PantryItem],
    *,
    pantry: PantryRepository,
) -> list[PantryItem]:
    """Store each item and return the saved items with their assigned ids."""
    saved = [pantry.add(item) for item in items]
    logger.info("Added %d pantry item(s)", len(saved))
    return saved


def remove_pantry_items(
    item_ids: Sequence[int],
    *,
    pantry: PantryRepository,
) -> list[PantryItem]:
    """Delete the items by id, all or nothing; return the pantry afterwards.

    Raises PantryItemNotFoundError naming every unknown id before anything is
    deleted, so a half-applied removal never has to be untangled.
    """
    stored = {item.id for item in pantry.list_all()}
    unknown = sorted(set(item_ids) - stored)
    if unknown:
        msg = f"Pantry item id(s) not found: {', '.join(map(str, unknown))}"
        raise PantryItemNotFoundError(msg)
    for item_id in dict.fromkeys(item_ids):
        pantry.delete(item_id)
    logger.info("Removed %d pantry item(s)", len(set(item_ids)))
    return pantry.list_all()
