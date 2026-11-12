from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from dispensa.app import queue_extraction
from dispensa.domain.enums import PendingStatus
from dispensa.domain.pending import PendingLink
from dispensa.settings import Settings
from dispensa.storage.batches_db import BatchRepository
from dispensa.storage.pending_db import PendingLinkRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_READY_CODES = {"AAAAAAAAAAA", "BBBBBBBBBBB"}


def _link(code: str, *, status: PendingStatus, caption: str | None) -> PendingLink:
    """Build a queued link in a given state."""
    return PendingLink(
        code=code,
        url=f"https://www.instagram.com/p/{code}/",
        caption=caption,
        status=status,
        created_at=_NOW,
    )


@pytest.fixture
def pending(db_engine: Engine) -> PendingLinkRepository:
    """Return a PendingLinkRepository on the clean test database."""
    return PendingLinkRepository(db_engine)


@pytest.fixture
def batches(db_engine: Engine) -> BatchRepository:
    """Return a BatchRepository on the clean test database."""
    return BatchRepository(db_engine)


@pytest.fixture
def _fake_openai(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Replace the OpenAI batch calls; record the codes each submission carried."""
    submitted: list[list[str]] = []
    batch_ids = iter(("batch_1", "batch_2", "batch_3"))

    def _write(items: list[PendingLink]) -> Path:
        submitted.append([item.code for item in items])
        return Path("unused.jsonl")

    def _create(_settings: Settings, *, input_path: Path) -> str:
        _ = input_path
        return next(batch_ids)

    monkeypatch.setattr(queue_extraction, "write_batch_input", _write)
    monkeypatch.setattr(queue_extraction, "create_batch", _create)
    return submitted


@pytest.mark.usefixtures("_fake_openai")
def test_launch_submits_ready_links_and_marks_them_extracting(
    pending: PendingLinkRepository,
    batches: BatchRepository,
) -> None:
    """Ready captioned links go into one batch; a new, caption-less link is left."""
    pending.add(_link("AAAAAAAAAAA", status=PendingStatus.READY, caption="a caption"))
    pending.add(_link("BBBBBBBBBBB", status=PendingStatus.READY, caption="b caption"))
    pending.add(_link("CCCCCCCCCCC", status=PendingStatus.NEW, caption=None))

    count = launch(pending, batches)

    assert count == len(_READY_CODES)
    extracting = {
        link.code: link
        for link in pending.list_all()
        if link.status is PendingStatus.EXTRACTING
    }
    assert set(extracting) == _READY_CODES
    assert all(link.batch_id == "batch_1" for link in extracting.values())

    still_new = pending.get("CCCCCCCCCCC")
    assert still_new is not None
    assert still_new.status is PendingStatus.NEW
    assert still_new.batch_id is None

    recorded = batches.latest()
    assert recorded is not None
    assert set(recorded.codes) == _READY_CODES


@pytest.mark.usefixtures("_fake_openai")
def test_launch_skips_links_already_in_a_batch(
    pending: PendingLinkRepository,
    batches: BatchRepository,
) -> None:
    """A second launch does not resubmit links already extracting."""
    pending.add(_link("AAAAAAAAAAA", status=PendingStatus.READY, caption="a caption"))

    assert launch(pending, batches) == 1
    # The link is now EXTRACTING and recorded in batch_1, so a second launch (even
    # after another link is marked READY again) never resubmits it.
    assert launch(pending, batches) == 0


@pytest.mark.usefixtures("_fake_openai")
def test_launch_honours_only_codes(
    pending: PendingLinkRepository,
    batches: BatchRepository,
) -> None:
    """only_codes restricts the submission to the named links."""
    pending.add(_link("AAAAAAAAAAA", status=PendingStatus.READY, caption="a caption"))
    pending.add(_link("BBBBBBBBBBB", status=PendingStatus.READY, caption="b caption"))

    count = launch(pending, batches, only_codes={"AAAAAAAAAAA"})

    assert count == 1
    untouched = pending.get("BBBBBBBBBBB")
    assert untouched is not None
    assert untouched.status is PendingStatus.READY


def test_launch_with_nothing_ready_returns_zero(
    pending: PendingLinkRepository,
    batches: BatchRepository,
) -> None:
    """No ready links means no batch and no OpenAI call."""
    pending.add(_link("CCCCCCCCCCC", status=PendingStatus.NEW, caption=None))

    assert launch(pending, batches) == 0


def launch(
    pending: PendingLinkRepository,
    batches: BatchRepository,
    *,
    only_codes: set[str] | None = None,
) -> int:
    """Call the use-case with a stub settings and the fixed clock."""
    return queue_extraction.launch_queue_extraction(
        Settings(openai_api_key="test-key"),
        pending=pending,
        batches=batches,
        now=_NOW,
        only_codes=only_codes,
    )
