from typing import TYPE_CHECKING

from sqlmodel import col, select

from foodiegram.domain.models import Extraction
from foodiegram.storage._tables import ExtractionRow
from foodiegram.storage.db import ensure_utc, get_session

if TYPE_CHECKING:
    from sqlalchemy import Engine


def _to_extraction(row: ExtractionRow) -> Extraction:
    """Map an extraction row back to the domain model, reviving the payload."""
    return Extraction.model_validate(
        {
            "id": row.id,
            "recipe_code": row.recipe_code,
            "prompt_version": row.prompt_version,
            "model": row.model,
            "batch_id": row.batch_id,
            "kind": row.kind,
            "extracted_at": ensure_utc(row.extracted_at),
            "payload": row.payload,
        },
    )


class ExtractionRepository:
    """Append-only store for immutable extraction runs. No update, no delete."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def add(self, extraction: Extraction) -> Extraction:
        """Append an extraction run and return it with its assigned id."""
        with get_session(self._engine) as session:
            row = ExtractionRow(
                recipe_code=extraction.recipe_code,
                prompt_version=extraction.prompt_version,
                model=extraction.model,
                batch_id=extraction.batch_id,
                kind=extraction.kind,
                extracted_at=extraction.extracted_at,
                payload=extraction.payload.model_dump(mode="json"),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_extraction(row)

    def latest_for(
        self,
        code: str,
        *,
        prompt_version: str | None = None,
    ) -> Extraction | None:
        """Return the newest extraction for code, optionally pinned to a version."""
        with get_session(self._engine) as session:
            statement = select(ExtractionRow).where(
                col(ExtractionRow.recipe_code) == code,
            )
            if prompt_version is not None:
                statement = statement.where(
                    col(ExtractionRow.prompt_version) == prompt_version,
                )
            statement = statement.order_by(col(ExtractionRow.id).desc())
            row = session.exec(statement).first()
            return _to_extraction(row) if row is not None else None

    def list_versions(self, code: str) -> list[str]:
        """Return the distinct prompt versions extracted for code, sorted."""
        with get_session(self._engine) as session:
            statement = (
                select(col(ExtractionRow.prompt_version))
                .where(col(ExtractionRow.recipe_code) == code)
                .distinct()
            )
            return sorted(session.exec(statement).all())

    def for_version(self, prompt_version: str) -> list[Extraction]:
        """Return every extraction at prompt_version, oldest first."""
        with get_session(self._engine) as session:
            statement = (
                select(ExtractionRow)
                .where(col(ExtractionRow.prompt_version) == prompt_version)
                .order_by(col(ExtractionRow.id))
            )
            return [_to_extraction(row) for row in session.exec(statement).all()]
