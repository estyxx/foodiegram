from datetime import UTC, date, datetime, timedelta, timezone
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from dispensa.api import create_app
from dispensa.deps import Deps
from dispensa.domain.exercise_log import ExerciseCategory, ExerciseCompletion
from dispensa.storage.exercise_log_db import ExerciseLogRepository
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository

_DAY = date(2026, 10, 12)
_NEXT_DAY = date(2026, 10, 13)
_MORNING = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
_NOON = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
_TWICE = 2


def _completion(
    client_id: str,
    *,
    exercise: str = "Pelvic Lift",
    done_on: date = _DAY,
    completed_at: datetime = _MORNING,
) -> ExerciseCompletion:
    """Build a Mobilize completion with a few overridable fields."""
    return ExerciseCompletion(
        client_id=client_id,
        exercise=exercise,
        category=ExerciseCategory.MOBILIZE,
        done_on=done_on,
        completed_at=completed_at,
    )


def _body(
    client_id: str,
    *,
    completed_at: str = "2026-10-12T08:00:00+00:00",
) -> dict[str, str]:
    """Build a valid POST body."""
    return {
        "client_id": client_id,
        "exercise": "Squat",
        "category": "Strengthen",
        "done_on": "2026-10-12",
        "completed_at": completed_at,
    }


@pytest.fixture
def repo(engine: Engine) -> ExerciseLogRepository:
    """Return the repository bound to the clean test database."""
    return ExerciseLogRepository(engine)


@pytest.fixture
def client(engine: Engine) -> TestClient:
    """Return a TestClient over an auth-disabled app."""
    deps = Deps(
        recipes=RecipeRepository(engine),
        extractions=ExtractionRepository(engine),
        user_state=UserStateRepository(engine),
        plans=PlanRepository(engine),
        pantry=PantryRepository(engine),
        targets=TargetRepository(engine),
        exercise_log=ExerciseLogRepository(engine),
    )
    return TestClient(create_app(deps=deps))


def test_same_exercise_can_be_logged_many_times_in_a_day(
    repo: ExerciseLogRepository,
) -> None:
    """Two taps on the same exercise, same day, are two distinct rows."""
    repo.add(_completion("a", completed_at=_MORNING))
    repo.add(_completion("b", completed_at=_NOON))

    logged = repo.list_for_day(_DAY)

    assert [entry.client_id for entry in logged] == ["a", "b"]
    assert {entry.exercise for entry in logged} == {"Pelvic Lift"}


def test_retried_client_id_does_not_duplicate(repo: ExerciseLogRepository) -> None:
    """Re-adding the same client_id returns the stored row and adds nothing."""
    first = repo.add(_completion("a"))
    again = repo.add(_completion("a"))

    assert again.id == first.id
    assert len(repo.list_for_day(_DAY)) == 1


def test_list_for_day_is_scoped_to_the_local_day(repo: ExerciseLogRepository) -> None:
    """Each day starts from zero: another day's completions are not returned."""
    repo.add(_completion("a", done_on=_DAY))
    repo.add(_completion("b", done_on=_NEXT_DAY))

    assert [entry.client_id for entry in repo.list_for_day(_NEXT_DAY)] == ["b"]
    assert repo.list_for_day(date(2026, 10, 14)) == []


def test_completed_at_round_trips_as_aware_utc(repo: ExerciseLogRepository) -> None:
    """The stored instant comes back timezone-aware, not naive."""
    rome_summer = timezone(timedelta(hours=2))
    repo.add(_completion("a", completed_at=_MORNING.astimezone(rome_summer)))

    (entry,) = repo.list_for_day(_DAY)

    assert entry.completed_at == _MORNING
    assert entry.completed_at.utcoffset() == timedelta(0)


def test_api_log_then_list(client: TestClient) -> None:
    """POST logs an entry; GET for that day returns it."""
    created = client.post("/api/exercise-log", json=_body("a"))

    assert created.status_code == HTTPStatus.CREATED
    listed = client.get("/api/exercise-log", params={"day": "2026-10-12"}).json()
    assert [(row["exercise"], row["category"]) for row in listed] == [
        ("Squat", "Strengthen"),
    ]


def test_api_resending_client_id_is_idempotent(client: TestClient) -> None:
    """A retried POST (lost response) does not inflate the day's count."""
    client.post("/api/exercise-log", json=_body("a"))
    client.post("/api/exercise-log", json=_body("a"))
    client.post("/api/exercise-log", json=_body("b"))

    listed = client.get("/api/exercise-log", params={"day": "2026-10-12"}).json()

    assert len(listed) == _TWICE


def test_api_rejects_unknown_category(client: TestClient) -> None:
    """A category outside the page's four groups is a 422, never stored."""
    body = _body("a") | {"category": "Yoga"}

    response = client.post("/api/exercise-log", json=body)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_api_rejects_naive_timestamp(client: TestClient) -> None:
    """completed_at must carry a timezone so the instant is unambiguous."""
    response = client.post(
        "/api/exercise-log",
        json=_body("a", completed_at="2026-10-12T08:00:00"),
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
