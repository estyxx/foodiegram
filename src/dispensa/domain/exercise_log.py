from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict


# No UNKNOWN member: the category is validated at the API edge, so a value outside
# the page's four groups is rejected rather than stored.
class ExerciseCategory(StrEnum):
    """The four back-exercise groups the standalone page rotates through."""

    MOBILIZE = "Mobilize"
    MOVE = "Move"
    STRENGTHEN = "Strengthen"
    ACTIVATE = "Activate"


class ExerciseCompletion(BaseModel):
    """One tap on 'Fatto': an exercise completed at a moment, on a local day."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Storage identity; None until persisted.
    id: int | None = None
    # Minted by the page per tap, so a retried POST is idempotent while two real
    # repeats of the same exercise stay two rows.
    client_id: str
    exercise: str
    category: ExerciseCategory
    # The user's local calendar day; the server cannot derive it from a UTC instant.
    done_on: date
    completed_at: AwareDatetime
