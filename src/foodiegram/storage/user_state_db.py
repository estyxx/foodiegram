from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlmodel import col, select

from foodiegram.domain.models import UserState
from foodiegram.storage._tables import UserStateRow
from foodiegram.storage.db import ensure_utc, get_session

if TYPE_CHECKING:
    from sqlalchemy import Engine


def _to_user_state(row: UserStateRow) -> UserState:
    """Map a user-state row to the domain model."""
    return UserState.model_validate(
        {
            "recipe_code": row.recipe_code,
            "is_favorite": row.is_favorite,
            "user_notes": row.user_notes,
            "updated_at": ensure_utc(row.updated_at),
        },
    )


class UserStateRepository:
    """Store for per-recipe app state (favourites, notes)."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def get(self, code: str) -> UserState | None:
        """Return the stored state for code, or None."""
        with get_session(self._engine) as session:
            row = session.get(UserStateRow, code)
            return _to_user_state(row) if row is not None else None

    def set_favorite(self, code: str, *, is_favorite: bool) -> UserState:
        """Upsert the favourite flag for code, keeping any existing notes."""
        now = datetime.now(tz=UTC)
        with get_session(self._engine) as session:
            row = session.get(UserStateRow, code)
            if row is None:
                row = UserStateRow(recipe_code=code, updated_at=now)
            row.is_favorite = is_favorite
            row.updated_at = now
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_user_state(row)

    def set_notes(self, code: str, *, notes: str | None) -> UserState:
        """Upsert the notes for code, keeping any existing favourite flag."""
        now = datetime.now(tz=UTC)
        with get_session(self._engine) as session:
            row = session.get(UserStateRow, code)
            if row is None:
                row = UserStateRow(recipe_code=code, updated_at=now)
            row.user_notes = notes
            row.updated_at = now
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_user_state(row)

    def all_favorites(self) -> list[str]:
        """Return the codes of all favourited recipes, sorted."""
        with get_session(self._engine) as session:
            statement = select(col(UserStateRow.recipe_code)).where(
                col(UserStateRow.is_favorite).is_(True),
            )
            return sorted(session.exec(statement).all())
