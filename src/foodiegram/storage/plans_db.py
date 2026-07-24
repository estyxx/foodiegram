from typing import TYPE_CHECKING, Literal

from sqlmodel import Session, col, select

from foodiegram.domain.errors import StorageError
from foodiegram.domain.planning import PlannedMeal, WeekPlan
from foodiegram.storage._tables import PlannedMealRow, WeekPlanRow
from foodiegram.storage.db import get_session

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy import Engine

# Lunch sorts before dinner within a day for stable plan output.
_MEAL_ORDER: dict[str, int] = {"lunch": 0, "dinner": 1}


def _to_meal(row: PlannedMealRow) -> PlannedMeal:
    """Map a planned-meal row to the domain model."""
    return PlannedMeal.model_validate(
        {
            "id": row.id,
            "day": row.day,
            "meal": row.meal,
            "recipe_code": row.recipe_code,
            "portions": row.portions,
        },
    )


class PlanRepository:
    """Store for week plans and their meal slots, keyed by Monday start date."""

    def __init__(self, engine: Engine) -> None:
        """Bind the repository to a database engine."""
        self._engine = engine

    def get(self, week_start: date) -> WeekPlan | None:
        """Return the plan for week_start, or None if none is stored."""
        with get_session(self._engine) as session:
            plan_row = self._plan_row(session, week_start)
            if plan_row is None:
                return None
            meal_rows = session.exec(
                select(PlannedMealRow).where(
                    col(PlannedMealRow.plan_id) == plan_row.id,
                ),
            ).all()
            meals = sorted(
                (_to_meal(row) for row in meal_rows),
                key=lambda meal: (meal.day, _MEAL_ORDER[meal.meal]),
            )
            return WeekPlan(week_start=plan_row.week_start, meals=tuple(meals))

    def upsert_meal(
        self,
        *,
        week_start: date,
        day: date,
        meal: Literal["lunch", "dinner"],
        recipe_code: str,
        portions: int,
    ) -> PlannedMeal:
        """Insert or replace the meal in (day, slot); create the plan if needed."""
        WeekPlan(week_start=week_start)  # reject a non-Monday before writing.
        with get_session(self._engine) as session:
            plan_row = self._plan_row(session, week_start)
            if plan_row is None:
                plan_row = WeekPlanRow(week_start=week_start)
                session.add(plan_row)
                session.commit()
                session.refresh(plan_row)
            plan_id = plan_row.id
            if plan_id is None:
                msg = "week plan row has no id after insert"
                raise StorageError(msg)

            row = session.exec(
                select(PlannedMealRow).where(
                    col(PlannedMealRow.plan_id) == plan_id,
                    col(PlannedMealRow.day) == day,
                    col(PlannedMealRow.meal) == meal,
                ),
            ).first()
            if row is None:
                row = PlannedMealRow(
                    plan_id=plan_id,
                    day=day,
                    meal=meal,
                    recipe_code=recipe_code,
                    portions=portions,
                )
            else:
                row.recipe_code = recipe_code
                row.portions = portions
            session.add(row)
            session.commit()
            session.refresh(row)
            return _to_meal(row)

    def delete_meal(self, week_start: date, meal_id: int) -> bool:
        """Delete meal_id from week_start's plan; return True if it existed."""
        with get_session(self._engine) as session:
            plan_row = self._plan_row(session, week_start)
            if plan_row is None:
                return False
            row = session.get(PlannedMealRow, meal_id)
            if row is None or row.plan_id != plan_row.id:
                return False
            session.delete(row)
            session.commit()
            return True

    @staticmethod
    def _plan_row(session: Session, week_start: date) -> WeekPlanRow | None:
        """Return the week_plans row for week_start within an open session."""
        return session.exec(
            select(WeekPlanRow).where(col(WeekPlanRow.week_start) == week_start),
        ).first()
