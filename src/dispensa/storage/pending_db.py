from datetime import UTC
from typing import TYPE_CHECKING

from sqlmodel import col, select

from dispensa.domain.enums import PendingStatus
from dispensa.domain.pending import PendingLink
from dispensa.storage._tables import PendingLinkRow
from dispensa.storage.db import ensure_utc, get_session

if TYPE_CHECKING:
    from sqlalchemy import Engine


def _to_link(row: PendingLinkRow) -> PendingLink:
    """Map a pending-link row to the domain model."""
    return PendingLink.model_validate(
        {
            "code": row.code,
            "url": row.url,
            "caption": row.caption,
            "thumbnail_url": row.thumbnail_url,
            "status": row.status,
            "batch_id": row.batch_id,
            "created_at": ensure_utc(row.created_at),
        },
    )


class PendingLinkRepository:
    """Store for the capture queue of shared links."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def add(self, link: PendingLink) -> PendingLink:
        """Insert a pending link (naive-UTC created_at, like the exercise log)."""
        with get_session(self._engine) as session:
            row = PendingLinkRow(
                code=link.code,
                url=link.url,
                caption=link.caption,
                thumbnail_url=link.thumbnail_url,
                status=link.status.value,
                batch_id=link.batch_id,
                created_at=link.created_at.astimezone(UTC).replace(tzinfo=None),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_link(row)

    def list_all(self) -> list[PendingLink]:
        """Return every pending link, newest first."""
        with get_session(self._engine) as session:
            rows = session.exec(
                select(PendingLinkRow).order_by(col(PendingLinkRow.created_at).desc()),
            ).all()
            return [_to_link(row) for row in rows]

    def get(self, code: str) -> PendingLink | None:
        """Return the pending link for code, or None."""
        with get_session(self._engine) as session:
            row = session.get(PendingLinkRow, code)
            return _to_link(row) if row is not None else None

    def set_caption(self, code: str, caption: str) -> PendingLink | None:
        """Store the pasted caption and mark the link ready; None if absent."""
        with get_session(self._engine) as session:
            row = session.get(PendingLinkRow, code)
            if row is None:
                return None
            row.caption = caption
            row.status = PendingStatus.READY.value
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_link(row)

    def mark(
        self,
        code: str,
        status: PendingStatus,
        *,
        batch_id: str | None = None,
    ) -> PendingLink | None:
        """Set a link's status (and optionally its batch id); None if absent."""
        with get_session(self._engine) as session:
            row = session.get(PendingLinkRow, code)
            if row is None:
                return None
            row.status = status.value
            if batch_id is not None:
                row.batch_id = batch_id
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_link(row)

    def delete(self, code: str) -> bool:
        """Delete the pending link for code; return True if it existed."""
        with get_session(self._engine) as session:
            row = session.get(PendingLinkRow, code)
            if row is None:
                return False
            session.delete(row)
            session.commit()
            return True
