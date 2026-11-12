"""add exercise_id to exercise log

Revision ID: 97703b5035c1
Revises: 7391519ae25e
Create Date: 2026-11-12 15:28:47.044464

"""

import re
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "97703b5035c1"
down_revision: str | Sequence[str] | None = "7391519ae25e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# A snapshot of each exercise's display name mapped to its stable catalog id, taken
# when the ids were introduced. Existing rows stored only the name, so this is how
# they get an id once. The live catalog (dispensa.exercise_routine) may diverge
# later; this migration keeps the one-time mapping it needs.
_NAME_TO_ID: dict[str, str] = {
    "Pelvic Lift": "pelvic-lift",
    "Knee Rolling": "knee-rolling",
    "Hip Flex": "hip-flex",
    "Knees to Chest": "knees-to-chest",
    "Sitting Forward Position": "sitting-forward-position",
    "Hip Extension": "hip-extension",
    "Forward Bend": "forward-bend",
    "Front Lying Back Lift": "front-lying-back-lift",
    "Cat / Camel": "cat-camel",
    "Child's Pose": "childs-pose",
    "Thread the Needle": "thread-the-needle",
    "Leg Cross Overs": "leg-cross-overs",
    "Marching": "marching",
    "Hip Up and Out": "hip-up-and-out",
    "Shoulder Blade Squeeze": "shoulder-blade-squeeze",
    "Standing Bow and Arrow": "standing-bow-and-arrow",
    "Static Glutes": "static-glutes",
    "Bilateral Bridge": "bilateral-bridge",
    "Offset Bridge": "offset-bridge",
    "Split Stance Hip Hinge": "split-stance-hip-hinge",
    "Forward Bend Hip Hinge": "forward-bend-hip-hinge",
    "Squat": "squat",
    "Jefferson Curl": "jefferson-curl",
    "Exercise Top End": "exercise-top-end",
    "Superman": "superman",
    "Deadbug": "deadbug",
    "Half Front Plank": "half-front-plank",
    "Half Side Plank": "half-side-plank",
    "Child's Pose + Extension": "childs-pose-extension",
    "Lunge and Twist": "lunge-and-twist",
}


def _slug(name: str) -> str:
    """Derive a stable id from an unknown name, so no row is left without one."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "unknown"


def upgrade() -> None:
    """Add exercise_id, backfill existing rows by name, then require it."""
    op.add_column(
        "exercise_log",
        sa.Column("exercise_id", sa.String(), nullable=True),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, exercise FROM exercise_log"),
    ).fetchall()
    for row_id, name in rows:
        exercise_id = _NAME_TO_ID.get(name) or _slug(name)
        connection.execute(
            sa.text("UPDATE exercise_log SET exercise_id = :x WHERE id = :i"),
            {"x": exercise_id, "i": row_id},
        )
    op.alter_column("exercise_log", "exercise_id", nullable=False)


def downgrade() -> None:
    """Drop exercise_id."""
    op.drop_column("exercise_log", "exercise_id")
