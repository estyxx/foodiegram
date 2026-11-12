from datetime import UTC, datetime

from sqlalchemy import Engine

from dispensa.domain.batch import BatchRun
from dispensa.domain.enums import BatchStatus
from dispensa.storage.batches_db import BatchRepository

_DAY_ONE = datetime(2026, 1, 1, tzinfo=UTC)
_DAY_TWO = datetime(2026, 1, 2, tzinfo=UTC)


def _run(batch_id: str, codes: tuple[str, ...], at: datetime = _DAY_ONE) -> BatchRun:
    """Build a submitted batch run."""
    return BatchRun(
        batch_id=batch_id,
        prompt_version="3",
        codes=codes,
        submitted_at=at,
    )


def test_record_round_trips(engine: Engine) -> None:
    """A recorded batch reads back with its codes and status."""
    repo = BatchRepository(engine)
    repo.record(_run("b1", ("A", "B")))

    got = repo.get("b1")

    assert got is not None
    assert got.codes == ("A", "B")
    assert got.status is BatchStatus.SUBMITTED


def test_latest_is_the_most_recently_submitted(engine: Engine) -> None:
    """latest() returns the newest batch by submitted_at."""
    repo = BatchRepository(engine)
    repo.record(_run("b1", ("A",), _DAY_ONE))
    repo.record(_run("b2", ("B",), _DAY_TWO))

    latest = repo.latest()

    assert latest is not None
    assert latest.batch_id == "b2"


def test_all_submitted_codes_unions_every_batch(engine: Engine) -> None:
    """Every code ever put in a batch is returned once."""
    repo = BatchRepository(engine)
    repo.record(_run("b1", ("A", "B")))
    repo.record(_run("b2", ("B", "C"), _DAY_TWO))

    assert repo.all_submitted_codes() == {"A", "B", "C"}


def test_mark_updates_status(engine: Engine) -> None:
    """mark() moves a batch to a new status."""
    repo = BatchRepository(engine)
    repo.record(_run("b1", ("A",)))

    repo.mark("b1", BatchStatus.APPLIED)

    got = repo.get("b1")
    assert got is not None
    assert got.status is BatchStatus.APPLIED
