from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from dispensa.api_models import PantryItemCreate, PantryItemOut
from dispensa.app.pantry import add_pantry_items, remove_pantry_items
from dispensa.deps import DepsDep
from dispensa.domain.errors import PantryItemNotFoundError
from dispensa.domain.pantry import PantryItem

router = APIRouter(prefix="/api/pantry")


def _to_out(item: PantryItem) -> PantryItemOut:
    """Shape a domain pantry item into its API response."""
    return PantryItemOut(
        id=item.id,
        name=item.name,
        kind=item.kind,
        location=item.location.value,
        quantity=item.quantity,
        expires=item.expires,
    )


@router.get("")
async def list_pantry(deps: DepsDep) -> list[PantryItemOut]:
    """Return every pantry item, ordered by name."""
    return [_to_out(item) for item in deps.pantry.list_all()]


@router.post("", status_code=201)
async def create_pantry_item(body: PantryItemCreate, deps: DepsDep) -> PantryItemOut:
    """Add a pantry item and return it with its assigned id."""
    (item,) = add_pantry_items(
        [
            PantryItem(
                name=body.name,
                kind=body.kind,
                location=body.location,
                quantity=body.quantity,
                expires=body.expires,
            ),
        ],
        pantry=deps.pantry,
    )
    return _to_out(item)


@router.delete("/{item_id}", status_code=204)
async def delete_pantry_item(item_id: int, deps: DepsDep) -> Response:
    """Delete a pantry item; 404 if it does not exist."""
    try:
        remove_pantry_items([item_id], pantry=deps.pantry)
    except PantryItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(status_code=204)
