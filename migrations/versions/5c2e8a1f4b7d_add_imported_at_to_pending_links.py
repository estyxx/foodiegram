"""add imported_at to pending_links

Revision ID: 5c2e8a1f4b7d
Revises: 1d6c9ba52f33
Create Date: 2026-11-25 22:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5c2e8a1f4b7d"
down_revision: str | Sequence[str] | None = "1d6c9ba52f33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add pending_links.imported_at, backfilled for links already imported.

    A link imported before this column existed takes its recipe's creation time,
    which is when the import saved it; without a recipe, its own queue time.
    """
    op.add_column("pending_links", sa.Column("imported_at", sa.DateTime(), nullable=True))
    op.execute(
        """
        UPDATE pending_links AS link
        SET imported_at = COALESCE(
            (SELECT recipe.created_at FROM recipes AS recipe WHERE recipe.code = link.code),
            link.created_at
        )
        WHERE link.status = 'imported'
        """,
    )


def downgrade() -> None:
    """Drop pending_links.imported_at."""
    op.drop_column("pending_links", "imported_at")
