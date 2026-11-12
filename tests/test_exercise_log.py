from datetime import UTC, date, datetime, timedelta, timezone
from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from dispensa.api import create_app
from dispensa.deps import Deps
from dispensa.domain.exercise_log import ExerciseCategory, ExerciseCompletion
from dispensa.exercise_routine import name_to_id
from dispensa.storage.batches_db import BatchRepository
from dispensa.storage.exercise_log_db import ExerciseLogRepository
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pantry_db import PantryRepository
from dispensa.storage.pending_db import PendingLinkRepository
from dispensa.storage.plans_db import PlanRepository
from dispensa.storage.recipes_db import RecipeRepository
from dispensa.storage.targets_db import TargetRepository
from dispensa.storage.user_state_db import UserStateRepository

_DAY = date(2026, 10, 12)
_NEXT_DAY = date(2026, 10, 13)
_MORNING = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
_NOON = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
_TWICE = 2
_ROUTINE_SIZE = 30


def _completion(
    client_id: str,
    *,
    exercise: str = "Pelvic Lift",
    exercise_id: str = "pelvic-lift",
    done_on: date = _DAY,
    completed_at: datetime = _MORNING,
) -> ExerciseCompletion:
    """Build a Mobilize completion with a few overridable fields."""
    return ExerciseCompletion(
        client_id=client_id,
        exercise_id=exercise_id,
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
        "exercise_id": "squat",
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
        pending=PendingLinkRepository(engine),
        batches=BatchRepository(engine),
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


def test_list_between_is_inclusive_and_bounded(repo: ExerciseLogRepository) -> None:
    """A week query returns both edges and nothing outside the range."""
    repo.add(_completion("before", done_on=date(2026, 10, 11)))
    repo.add(_completion("monday", done_on=date(2026, 10, 12)))
    repo.add(_completion("sunday", done_on=date(2026, 10, 18)))
    repo.add(_completion("after", done_on=date(2026, 10, 19)))

    week = repo.list_between(start=date(2026, 10, 12), end=date(2026, 10, 18))

    assert [entry.client_id for entry in week] == ["monday", "sunday"]


def test_api_range_spans_days(client: TestClient) -> None:
    """GET /range returns every completion across the requested days."""
    client.post("/api/exercise-log", json=_body("a"))
    other_day = _body("b") | {"done_on": "2026-10-14"}
    client.post("/api/exercise-log", json=other_day)

    listed = client.get(
        "/api/exercise-log/range",
        params={"start": "2026-10-12", "end": "2026-10-18"},
    ).json()

    assert [row["done_on"] for row in listed] == ["2026-10-12", "2026-10-14"]


@pytest.mark.parametrize(
    ("start", "end"),
    [("2026-10-18", "2026-10-12"), ("2026-01-01", "2026-12-31")],
)
def test_api_range_rejects_reversed_or_huge_spans(
    client: TestClient,
    start: str,
    end: str,
) -> None:
    """A reversed or year-wide range is a 422, not a table scan."""
    response = client.get(
        "/api/exercise-log/range",
        params={"start": start, "end": end},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_routine_endpoint_lists_the_catalog(client: TestClient) -> None:
    """GET /routine returns the four categories, each exercise carrying an id."""
    body = client.get("/api/exercise-log/routine").json()

    assert [c["name"] for c in body] == ["Mobilize", "Move", "Strengthen", "Activate"]
    exercises = [ex for cat in body for ex in cat["exercises"]]
    assert len(exercises) == _ROUTINE_SIZE
    assert all(ex["id"] and ex["name"] for ex in exercises)
    ids = [ex["id"] for ex in exercises]
    assert len(set(ids)) == len(ids)


def test_history_is_linked_by_exercise_id_not_name(repo: ExerciseLogRepository) -> None:
    """Completions of one exercise group by id, so a renamed exercise keeps history."""
    repo.add(_completion("c1", exercise="Squat", exercise_id="squat"))
    repo.add(
        _completion(
            "c2",
            exercise="Back Squat",  # the display name changed later
            exercise_id="squat",
            done_on=_NEXT_DAY,
        ),
    )

    rows = repo.list_between(start=_DAY, end=_NEXT_DAY)

    assert {row.exercise_id for row in rows} == {"squat"}
    assert {row.exercise for row in rows} == {"Squat", "Back Squat"}


def test_catalog_names_map_to_stable_ids() -> None:
    """Every routine name resolves to a unique id (the backfill mapping source)."""
    mapping = name_to_id()
    assert len(mapping) == _ROUTINE_SIZE
    assert len(set(mapping.values())) == _ROUTINE_SIZE
    assert mapping["Squat"] == "squat"
