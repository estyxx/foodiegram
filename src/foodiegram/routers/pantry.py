from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from foodiegram.api_models import PantryItemCreate, PantryItemOut
from foodiegram.deps import DepsDep
from foodiegram.domain.pantry import PantryItem

router = APIRouter(prefix="/api/pantry")


def _to_out(item: PantryItem) -> PantryItemOut:
    """Shape a domain pantry item into its API response."""
    return PantryItemOut(
        id=item.id,
        name=item.name,
        kind=item.kind,
        expires=item.expires,
    )


@router.get("")
async def list_pantry(deps: DepsDep) -> list[PantryItemOut]:
    """Return every pantry item, ordered by name."""
    return [_to_out(item) for item in deps.pantry.list_all()]


@router.post("", status_code=201)
async def create_pantry_item(body: PantryItemCreate, deps: DepsDep) -> PantryItemOut:
    """Add a pantry item and return it with its assigned id."""
    item = deps.pantry.add(
        PantryItem(name=body.name, kind=body.kind, expires=body.expires),
    )
    return _to_out(item)


@router.delete("/{item_id}", status_code=204)
async def delete_pantry_item(item_id: int, deps: DepsDep) -> Response:
    """Delete a pantry item; 404 if it does not exist."""
    if not deps.pantry.delete(item_id):
        msg = f"Pantry item {item_id} not found"
        raise HTTPException(status_code=404, detail=msg)
    return Response(status_code=204)
