import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from foodiegram.ai import batch
from foodiegram.settings import Settings


class _FakeFiles:
    """Records uploaded batch input bytes and returns a canned file id."""

    def __init__(self) -> None:
        self.uploaded: list[bytes] = []

    def create(self, *, file: object, purpose: str) -> SimpleNamespace:
        assert purpose == "batch"
        self.uploaded.append(file.read())  # type: ignore[attr-defined]
        return SimpleNamespace(id="file_abc")


class _FakeBatches:
    """Returns a fixed batch id, mirroring the OpenAI Batch API response shape."""

    def __init__(self, batch_id: str) -> None:
        self._batch_id = batch_id

    def create(
        self, *, input_file_id: str, endpoint: str, completion_window: str
    ) -> SimpleNamespace:
        _ = (input_file_id, endpoint, completion_window)
        return SimpleNamespace(id=self._batch_id)


class _FakeOpenAI:
    """Stands in for the OpenAI client, exposing only files/batches used here."""

    def __init__(self, *, api_key: str, batch_id: str = "batch_123") -> None:
        _ = api_key
        self.files = _FakeFiles()
        self.batches = _FakeBatches(batch_id)


def _fake_openai_factory(batch_id: str) -> type[_FakeOpenAI]:
    def _factory(*, api_key: str) -> _FakeOpenAI:
        return _FakeOpenAI(api_key=api_key, batch_id=batch_id)

    return _factory  # type: ignore[return-value]


def test_create_batch_archives_input_by_batch_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The uploaded input is copied to a batch_id-keyed file, not just overwritten."""
    archive_dir = tmp_path / "batch_inputs"
    input_path = tmp_path / "batch_input.jsonl"
    input_path.write_text('{"custom_id": "ABC"}\n', encoding="utf-8")

    monkeypatch.setattr(batch, "BATCH_INPUT_ARCHIVE_DIR", archive_dir)
    monkeypatch.setattr(batch, "LAST_BATCH_ID_PATH", tmp_path / "last_batch_id.txt")
    monkeypatch.setattr(batch, "OpenAI", _fake_openai_factory("batch_6a849e5f"))

    settings = Settings(openai_api_key="test-key")
    batch_id = batch.create_batch(settings, input_path=input_path)

    assert batch_id == "batch_6a849e5f"
    archived = archive_dir / "batch_6a849e5f.jsonl"
    assert archived.read_text(encoding="utf-8") == input_path.read_text(encoding="utf-8")


def test_submitted_codes_unions_every_archived_batch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """submitted_codes reads custom_id across all archived batch files, deduped."""
    archive_dir = tmp_path / "batch_inputs"
    archive_dir.mkdir()
    (archive_dir / "batch_1.jsonl").write_text(
        json.dumps({"custom_id": "ABC"}) + "\n" + json.dumps({"custom_id": "DEF"}),
        encoding="utf-8",
    )
    (archive_dir / "batch_2.jsonl").write_text(
        json.dumps({"custom_id": "DEF"}) + "\n\n" + json.dumps({"custom_id": "GHI"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(batch, "BATCH_INPUT_ARCHIVE_DIR", archive_dir)

    assert batch.submitted_codes() == {"ABC", "DEF", "GHI"}


def test_submitted_codes_returns_empty_when_no_batches_yet(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No archived batches means nothing is excluded on the first-ever submission."""
    monkeypatch.setattr(batch, "BATCH_INPUT_ARCHIVE_DIR", tmp_path / "batch_inputs")

    assert batch.submitted_codes() == set()
