"""add language to recipes

Revision ID: 1d6c9ba52f33
Revises: 97703b5035c1
Create Date: 2026-11-12 20:50:15.684947

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "1d6c9ba52f33"
down_revision: str | Sequence[str] | None = "97703b5035c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add recipes.language, defaulting existing rows to Italian."""
    op.add_column(
        "recipes",
        sa.Column("language", sa.String(), nullable=False, server_default="it"),
    )


def downgrade() -> None:
    """Drop recipes.language."""
    op.drop_column("recipes", "language")
