from fastapi import APIRouter, HTTPException

from foodiegram.api_models import TargetOut, TargetsUpdate
from foodiegram.deps import DepsDep
from foodiegram.domain.enums import MedCategory
from foodiegram.domain.planning import CategoryTarget

router = APIRouter(prefix="/api/targets")


def _to_out(target: CategoryTarget) -> TargetOut:
    """Shape a domain target into its API response."""
    return TargetOut(
        category=target.category.value,
        min_servings=target.min_servings,
        max_servings=target.max_servings,
    )


@router.get("")
async def get_targets(deps: DepsDep) -> list[TargetOut]:
    """Return the weekly per-category serving targets."""
    return [_to_out(target) for target in deps.targets.list_all()]


@router.put("")
async def put_targets(body: TargetsUpdate, deps: DepsDep) -> list[TargetOut]:
    """Replace the weekly targets; unknown categories are rejected with 422."""
    try:
        targets = [
            CategoryTarget(
                category=MedCategory(entry.category),
                min_servings=entry.min_servings,
                max_servings=entry.max_servings,
            )
            for entry in body.targets
        ]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid target category") from exc
    return [_to_out(target) for target in deps.targets.set_all(targets)]
