import json
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine

from dispensa.ai.batch import PROMPT_VERSION, BatchOutput
from dispensa.app import queue_import
from dispensa.domain.batch import BatchRun
from dispensa.domain.enums import BatchStatus, PendingStatus
from dispensa.domain.models import ExtractedRecipe
from dispensa.domain.pending import PendingLink
from dispensa.settings import Settings
from dispensa.storage.batches_db import BatchRepository
from dispensa.storage.extractions_db import ExtractionRepository
from dispensa.storage.pending_db import PendingLinkRepository
from dispensa.storage.recipes_db import RecipeRepository

_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_BATCH_ID = "batch_1"
_MODEL = "gpt-5.4-mini-2026-03-17"
_A = "AAAAAAAAAAA"
_B = "BBBBBBBBBBB"


def _link(code: str) -> PendingLink:
    """Build an extracting queue link awaiting its batch result."""
    return PendingLink(
        code=code,
        url=f"https://www.instagram.com/p/{code}/",
        caption=f"caption for {code}",
        status=PendingStatus.EXTRACTING,
        batch_id=_BATCH_ID,
        created_at=_NOW,
    )


def _batch_line(code: str, extracted: ExtractedRecipe) -> str:
    """Build one OpenAI Batch output JSONL line for a Responses API result."""
    body: dict[str, object] = {
        "model": _MODEL,
        "output": [
            {"type": "reasoning"},
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": extracted.model_dump_json()}
                ],
            },
        ],
    }
    return json.dumps({"custom_id": code, "response": {"body": body}})


@pytest.fixture
def repos(
    db_engine: Engine,
) -> tuple[
    PendingLinkRepository,
    RecipeRepository,
    ExtractionRepository,
    BatchRepository,
]:
    """Return the four repositories on the clean test database."""
    return (
        PendingLinkRepository(db_engine),
        RecipeRepository(db_engine),
        ExtractionRepository(db_engine),
        BatchRepository(db_engine),
    )


def _patch_output(monkeypatch: pytest.MonkeyPatch, *lines: str) -> None:
    """Make fetch_batch_output return a completed batch with the given lines."""
    output = BatchOutput(batch_id=_BATCH_ID, content="\n".join(lines))
    monkeypatch.setattr(
        queue_import,
        "fetch_batch_output",
        lambda _settings, _batch_id: output,
    )


def _run(
    repos: tuple[
        PendingLinkRepository,
        RecipeRepository,
        ExtractionRepository,
        BatchRepository,
    ],
) -> int:
    """Call the import use-case with a stub settings and the fixed clock."""
    pending, recipes, extractions, batches = repos
    return queue_import.import_finished_queue(
        Settings(openai_api_key="test-key"),
        pending=pending,
        recipes=recipes,
        extractions=extractions,
        batches=batches,
        now=_NOW,
    )


def test_import_builds_recipes_and_marks_links_imported(
    repos: tuple[
        PendingLinkRepository,
        RecipeRepository,
        ExtractionRepository,
        BatchRepository,
    ],
    make_extracted: Callable[..., ExtractedRecipe],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A finished batch becomes recipes; the links flip to IMPORTED."""
    pending, recipes, extractions, batches = repos
    pending.add(_link(_A))
    batches.record(
        BatchRun(
            batch_id=_BATCH_ID,
            prompt_version=PROMPT_VERSION,
            codes=(_A,),
            submitted_at=_NOW,
        ),
    )
    _patch_output(monkeypatch, _batch_line(_A, make_extracted(title="Pasta e ceci")))

    assert _run(repos) == 1

    recipe = recipes.get(_A)
    assert recipe is not None
    assert recipe.title == "Pasta e ceci"
    assert recipe.caption == f"caption for {_A}"

    link = pending.get(_A)
    assert link is not None
    assert link.status is PendingStatus.IMPORTED
    assert extractions.latest_for(_A) is not None

    recorded = batches.get(_BATCH_ID)
    assert recorded is not None
    assert recorded.status is BatchStatus.APPLIED


def test_import_is_idempotent_and_skips_unknown_codes(
    repos: tuple[
        PendingLinkRepository,
        RecipeRepository,
        ExtractionRepository,
        BatchRepository,
    ],
    make_extracted: Callable[..., ExtractedRecipe],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second import adds nothing; a result for a non-queued code is ignored."""
    pending, recipes, extractions, batches = repos
    pending.add(_link(_A))
    batches.record(
        BatchRun(
            batch_id=_BATCH_ID,
            prompt_version=PROMPT_VERSION,
            codes=(_A,),
            submitted_at=_NOW,
        ),
    )
    _patch_output(
        monkeypatch,
        _batch_line(_A, make_extracted(title="Pasta e ceci")),
        _batch_line(_B, make_extracted(title="Not in the queue")),
    )

    assert _run(repos) == 1
    assert recipes.get(_B) is None

    # Second run: _A is IMPORTED now, so nothing is re-imported or re-appended.
    assert _run(repos) == 0
    assert len(extractions.for_version(PROMPT_VERSION)) == 1


def test_import_returns_zero_when_the_batch_is_not_ready(
    repos: tuple[
        PendingLinkRepository,
        RecipeRepository,
        ExtractionRepository,
        BatchRepository,
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No output (batch still running) imports nothing."""
    pending, _recipes, _extractions, _batches = repos
    pending.add(_link(_A))
    monkeypatch.setattr(
        queue_import,
        "fetch_batch_output",
        lambda _settings, _batch_id: None,
    )

    assert _run(repos) == 0
    link = pending.get(_A)
    assert link is not None
    assert link.status is PendingStatus.EXTRACTING
