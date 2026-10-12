from datetime import date

from fastapi import APIRouter

from dispensa.api_models import ExerciseLogCreate, ExerciseLogOut
from dispensa.deps import DepsDep
from dispensa.domain.exercise_log import ExerciseCompletion

router = APIRouter(prefix="/api/exercise-log")


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
