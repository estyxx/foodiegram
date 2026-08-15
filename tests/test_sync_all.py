import pytest

from foodiegram.app.sync_all import Stage, run_stages
from foodiegram.domain.errors import ExtractionError


def _stage(name: str, calls: list[str], *, boom: bool = False) -> Stage:
    """Build a stage that records its run and optionally raises."""

    def run() -> str:
        calls.append(name)
        if boom:
            msg = f"{name} failed"
            raise ExtractionError(msg)
        return f"{name}-ok"

    return Stage(name=name, run=run)


def test_run_stages_runs_every_stage_in_order() -> None:
    """All stages run in sequence and their summaries are returned."""
    calls: list[str] = []
    stages = [_stage(name, calls) for name in ("ingest", "extract", "promote", "embed")]

    summaries = run_stages(stages)

    assert calls == ["ingest", "extract", "promote", "embed"]
    assert summaries == [
        "ingest: ingest-ok",
        "extract: extract-ok",
        "promote: promote-ok",
        "embed: embed-ok",
    ]


def test_run_stages_stops_at_first_error() -> None:
    """A raising stage halts the pipeline; later stages never run."""
    calls: list[str] = []
    stages = [
        _stage("ingest", calls),
        _stage("extract", calls, boom=True),
        _stage("promote", calls),
    ]

    with pytest.raises(ExtractionError):
        run_stages(stages)

    assert calls == ["ingest", "extract"]
