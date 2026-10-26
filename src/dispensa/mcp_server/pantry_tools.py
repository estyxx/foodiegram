import logging
from typing import Annotated, Any

from pydantic import Field

from dispensa.api_models import PantryItemCreate
from dispensa.app.pantry import add_pantry_items as add_pantry_items_use_case
from dispensa.app.pantry import remove_pantry_items as remove_pantry_items_use_case
from dispensa.domain.errors import PantryItemNotFoundError
from dispensa.domain.pantry import PantryItem
from dispensa.mcp_server.runtime import get_deps, mcp
from dispensa.mcp_server.serializers import to_mcp_pantry

logger = logging.getLogger(__name__)


@mcp.tool()
def get_pantry() -> list[dict[str, Any]]:
    """Return everything in the kitchen, ordered by name.

    Each item has an `id` (what remove_pantry_items takes), `name`, `kind`
    (staple or fresh), `location` (fridge, freezer, pantry, or unknown), a
    free-text `quantity`, and `expires` (ISO date or null).
    """
    logger.info("get_pantry")
    return to_mcp_pantry(get_deps().pantry.list_all())


@mcp.tool()
def add_pantry_items(
    *,
    items: Annotated[
        list[PantryItemCreate],
        Field(
            description=(
                "Items to add. Each needs `name` (as the user says it, any "
                "language) and `kind`: 'staple' for long-lasting basics (oil, "
                "pasta, tins), 'fresh' for perishables. Optional: `location` "
                "('fridge', 'freezer', 'pantry'), free-text `quantity` "
                "('half a jar', '500 g'), and `expires` as 'YYYY-MM-DD'."
            ),
            min_length=1,
        ),
    ],
) -> list[dict[str, Any]]:
    """Add items to the pantry and return the whole pantry afterwards.

    Adding does not merge with an item of the same name; to change one,
    remove it and add it again.
    """
    logger.info("add_pantry_items: %d item(s)", len(items))
    pantry = get_deps().pantry
    add_pantry_items_use_case(
        [
            PantryItem(
                name=item.name,
                kind=item.kind,
                location=item.location,
                quantity=item.quantity,
                expires=item.expires,
            )
            for item in items
        ],
        pantry=pantry,
    )
    return to_mcp_pantry(pantry.list_all())


@mcp.tool()
def remove_pantry_items(
    *,
    ids: Annotated[
        list[int],
        Field(
            description="The `id`s to remove, from get_pantry or get_planning_context.",
            min_length=1,
        ),
    ],
) -> list[dict[str, Any]]:
    """Remove used-up items by id and return the whole pantry afterwards.

    All or nothing: if any id is unknown, nothing is removed and the error
    names the unknown ids.
    """
    logger.info("remove_pantry_items: ids=%s", ids)
    try:
        remaining = remove_pantry_items_use_case(ids, pantry=get_deps().pantry)
    except PantryItemNotFoundError as exc:
        msg = f"{exc}. Call get_pantry for the current ids."
        raise ValueError(msg) from exc
    return to_mcp_pantry(remaining)
