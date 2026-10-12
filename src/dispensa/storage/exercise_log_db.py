from datetime import UTC, date
from typing import TYPE_CHECKING

from sqlmodel import col, select

from dispensa.domain.exercise_log import ExerciseCompletion
from dispensa.storage._tables import ExerciseLogRow
from dispensa.storage.db import ensure_utc, get_session

if TYPE_CHECKING:
    from sqlalchemy import Engine


def _to_completion(row: ExerciseLogRow) -> ExerciseCompletion:
    """Map an exercise-log row to the domain model."""
    return ExerciseCompletion.model_validate(
        {
            "id": row.id,
            "client_id": row.client_id,
            "exercise": row.exercise,
            "category": row.category,
            "done_on": row.done_on,
            "completed_at": ensure_utc(row.completed_at),
        },
    )


class ExerciseLogRepository:
    """Append-only store for completed back exercises."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def add(self, entry: ExerciseCompletion) -> ExerciseCompletion:
        """Insert a completion; a repeated client_id returns the stored row."""
        with get_session(self._engine) as session:
            existing = session.exec(
                select(ExerciseLogRow).where(
                    col(ExerciseLogRow.client_id) == entry.client_id,
                ),
            ).first()
            if existing is not None:
                return _to_completion(existing)
            row = ExerciseLogRow(
                client_id=entry.client_id,
                exercise=entry.exercise,
                category=entry.category.value,
                done_on=entry.done_on,
                # Naive UTC on purpose: the column is `timestamp`, and psycopg2 would
                # shift an aware value into the session TimeZone before storing it.
                completed_at=entry.completed_at.astimezone(UTC).replace(tzinfo=None),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_completion(row)

    def list_for_day(self, day: date) -> list[ExerciseCompletion]:
        """Return the completions logged for day, oldest first."""
        with get_session(self._engine) as session:
            rows = session.exec(
                select(ExerciseLogRow)
                .where(col(ExerciseLogRow.done_on) == day)
                .order_by(col(ExerciseLogRow.completed_at), col(ExerciseLogRow.id)),
            ).all()
            return [_to_completion(row) for row in rows]
