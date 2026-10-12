from datetime import date

from fastapi import APIRouter, HTTPException

from dispensa.api_models import ExerciseLogCreate, ExerciseLogOut
from dispensa.deps import DepsDep
from dispensa.domain.exercise_log import ExerciseCompletion

router = APIRouter(prefix="/api/exercise-log")

# A week view needs 7 days; the cap only keeps a typo from reading the whole table.
_MAX_RANGE_DAYS = 31
_BAD_RANGE = f"end must not precede start, and span at most {_MAX_RANGE_DAYS} days"


def _to_out(entry: ExerciseCompletion) -> ExerciseLogOut:
    """Shape a domain completion into its API response."""
    return ExerciseLogOut(
        id=entry.id,
        client_id=entry.client_id,
        exercise=entry.exercise,
        category=entry.category.value,
        done_on=entry.done_on,
        completed_at=entry.completed_at,
    )


@router.get("")
async def list_exercise_log(day: date, deps: DepsDep) -> list[ExerciseLogOut]:
    """Return the completions logged for one local day, oldest first."""
    return [_to_out(entry) for entry in deps.exercise_log.list_for_day(day)]


@router.get("/range")
async def list_exercise_log_range(
    start: date,
    end: date,
    deps: DepsDep,
) -> list[ExerciseLogOut]:
    """Return completions from start to end inclusive, oldest first."""
    if end < start or (end - start).days >= _MAX_RANGE_DAYS:
        raise HTTPException(status_code=422, detail=_BAD_RANGE)
    entries = deps.exercise_log.list_between(start=start, end=end)
    return [_to_out(entry) for entry in entries]


@router.post("", status_code=201)
async def log_exercise(body: ExerciseLogCreate, deps: DepsDep) -> ExerciseLogOut:
    """Log a completed exercise; re-sending the same client_id is a no-op."""
    entry = deps.exercise_log.add(
        ExerciseCompletion(
            client_id=body.client_id,
            exercise=body.exercise,
            category=body.category,
            done_on=body.done_on,
            completed_at=body.completed_at,
        ),
    )
    return _to_out(entry)
