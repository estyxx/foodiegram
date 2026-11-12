from datetime import UTC
from typing import TYPE_CHECKING

from sqlmodel import col, select

from dispensa.domain.batch import BatchRun
from dispensa.storage._tables import BatchRunRow
from dispensa.storage.db import ensure_utc, get_session

if TYPE_CHECKING:
    from sqlalchemy import Engine

    from dispensa.domain.enums import BatchStatus


def _to_run(row: BatchRunRow) -> BatchRun:
    """Map a batch-run row to the domain model."""
    return BatchRun.model_validate(
        {
            "batch_id": row.batch_id,
            "prompt_version": row.prompt_version,
            "codes": tuple(row.codes),
            "status": row.status,
            "submitted_at": ensure_utc(row.submitted_at),
        },
    )


class BatchRepository:
    """Store for submitted extraction batches (DB-backed; no disk state)."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def record(self, run: BatchRun) -> BatchRun:
        """Insert a submitted batch (naive-UTC submitted_at, like the rest)."""
        with get_session(self._engine) as session:
            row = BatchRunRow(
                batch_id=run.batch_id,
                prompt_version=run.prompt_version,
                codes=list(run.codes),
                status=run.status.value,
                submitted_at=run.submitted_at.astimezone(UTC).replace(tzinfo=None),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_run(row)

    def latest(self) -> BatchRun | None:
        """Return the most recently submitted batch, or None."""
        with get_session(self._engine) as session:
            row = session.exec(
                select(BatchRunRow).order_by(col(BatchRunRow.submitted_at).desc()),
            ).first()
            return _to_run(row) if row is not None else None

    def get(self, batch_id: str) -> BatchRun | None:
        """Return the batch for batch_id, or None."""
        with get_session(self._engine) as session:
            row = session.get(BatchRunRow, batch_id)
            return _to_run(row) if row is not None else None

    def all_submitted_codes(self) -> set[str]:
        """Return every recipe code that has ever been put in a batch."""
        with get_session(self._engine) as session:
            rows = session.exec(select(BatchRunRow)).all()
            return {code for row in rows for code in row.codes}

    def mark(self, batch_id: str, status: BatchStatus) -> BatchRun | None:
        """Set a batch's status; None if it is not recorded."""
        with get_session(self._engine) as session:
            row = session.get(BatchRunRow, batch_id)
            if row is None:
                return None
            row.status = status.value
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_run(row)
