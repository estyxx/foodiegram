import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from dispensa import cli
from dispensa.domain.errors import ExtractionError
from dispensa.settings import Settings

runner = CliRunner()

_LOCAL_URL = "postgresql+psycopg2://dispensa:dispensa@localhost:5432/dispensa"
_PROD_URL = "postgresql+psycopg2://u:p@ep-x-pooler.eu-west-2.aws.neon.tech/neondb"


class _Calls:
    """Records the kwargs each faked stage was invoked with."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.ingest_dry: bool | None = None
        self.extract_dry: bool | None = None
        self.extract_only_missing: bool | None = None
        self.promote_dry: bool | None = None
        self.embed_dry: bool | None = None
        self.configured: bool = False


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> _Calls:
    """Stub out every side-effecting collaborator of `sync all`, recording calls."""
    rec = _Calls()

    settings = Settings(
        _env_file=None,
        database_url=_LOCAL_URL,
        openai_api_key="test-key",
        cloudinary_cloud_name="c",
        cloudinary_api_key="k",
        cloudinary_api_secret="s",
    )
    monkeypatch.setattr(cli, "_settings", lambda: settings)
    monkeypatch.setattr(cli, "create_db_engine", lambda _url: object())
    monkeypatch.setattr(cli, "init_db", lambda _engine: None)
    monkeypatch.setattr(cli, "RecipeRepository", lambda _engine: object())
    monkeypatch.setattr(cli, "ExtractionRepository", lambda _engine: object())
    monkeypatch.setattr(cli, "OpenAI", lambda **_kw: object())

    def _configure(*, config: object) -> None:
        _ = config
        rec.configured = True

    monkeypatch.setattr(cli, "configure", _configure)

    def _parse_food_items(*, path: Path) -> list[object]:
        _ = path
        return []

    def _ingest_food_json(
        *, recipes: object, items: object, upload: object, dry_run: bool
    ) -> object:
        _ = recipes, items, upload
        rec.order.append("ingest")
        rec.ingest_dry = dry_run
        return SimpleNamespace(new=1, caption_changed=0, image_fixed=0, unchanged=2)

    monkeypatch.setattr("dispensa.app.ingest.parse_food_items", _parse_food_items)
    monkeypatch.setattr("dispensa.app.ingest.ingest_food_json", _ingest_food_json)

    def _submit_batch(
        settings: object,
        *,
        recipes: object,
        extractions: object,
        only_missing: bool,
        dry_run: bool,
    ) -> int:
        _ = settings, recipes, extractions
        rec.order.append("extract")
        rec.extract_dry = dry_run
        rec.extract_only_missing = only_missing
        return 0

    monkeypatch.setattr("dispensa.app.extraction.submit_batch", _submit_batch)

    def _promote_version(
        *, recipes: object, extractions: object, version: str, dry_run: bool
    ) -> object:
        _ = recipes, extractions, version
        rec.order.append("promote")
        rec.promote_dry = dry_run
        return SimpleNamespace(promoted=0, changed=0)

    monkeypatch.setattr("dispensa.app.promotion.promote_version", _promote_version)

    def _embed_recipes(*, recipes: object, client: object, dry_run: bool) -> object:
        _ = recipes, client
        rec.order.append("embed")
        rec.embed_dry = dry_run
        return SimpleNamespace(embedded=0, needs_embedding=0)

    monkeypatch.setattr("dispensa.app.embed.embed_recipes", _embed_recipes)

    return rec


def _food_json(tmp_path: Path) -> Path:
    """Write a throwaway food.json (its contents are never parsed here)."""
    path = tmp_path / "food.json"
    path.write_text(json.dumps({"items": []}), encoding="utf-8")
    return path


def test_sync_all_runs_every_stage_in_order(calls: _Calls, tmp_path: Path) -> None:
    """The happy path runs ingest -> extract -> promote -> embed and configures."""
    result = runner.invoke(cli.app, ["sync", "all", str(_food_json(tmp_path))])

    assert result.exit_code == 0, result.output
    assert calls.order == ["ingest", "extract", "promote", "embed"]
    assert calls.configured is True
    assert calls.ingest_dry is False
    assert calls.extract_dry is False
    assert calls.extract_only_missing is True
    assert calls.promote_dry is False
    assert calls.embed_dry is False
    assert "async batch" in result.output


def test_sync_all_dry_run_propagates_to_every_stage(
    calls: _Calls, tmp_path: Path
) -> None:
    """--dry-run reaches all four stages and skips Cloudinary configuration."""
    result = runner.invoke(
        cli.app, ["sync", "all", str(_food_json(tmp_path)), "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert calls.order == ["ingest", "extract", "promote", "embed"]
    assert calls.configured is False
    assert calls.ingest_dry is True
    assert calls.extract_dry is True
    assert calls.promote_dry is True
    assert calls.embed_dry is True


def test_sync_all_refuses_a_prod_database_without_yes(
    calls: _Calls, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Neon-looking URL aborts before any stage runs unless --yes is given."""
    settings = Settings(
        _env_file=None,
        database_url=_PROD_URL,
        openai_api_key="test-key",
        cloudinary_cloud_name="c",
        cloudinary_api_key="k",
        cloudinary_api_secret="s",
    )
    monkeypatch.setattr(cli, "_settings", lambda: settings)

    result = runner.invoke(cli.app, ["sync", "all", str(_food_json(tmp_path))])

    assert result.exit_code == 1
    assert calls.order == []
    assert "prod" in result.output.lower()


def test_sync_all_with_yes_writes_to_a_prod_database(
    calls: _Calls, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--yes lifts the prod guard and the stages run."""
    settings = Settings(
        _env_file=None,
        database_url=_PROD_URL,
        openai_api_key="test-key",
        cloudinary_cloud_name="c",
        cloudinary_api_key="k",
        cloudinary_api_secret="s",
    )
    monkeypatch.setattr(cli, "_settings", lambda: settings)

    result = runner.invoke(cli.app, ["sync", "all", str(_food_json(tmp_path)), "--yes"])

    assert result.exit_code == 0, result.output
    assert calls.order == ["ingest", "extract", "promote", "embed"]


def test_sync_all_stops_at_the_first_failing_stage(
    calls: _Calls, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DispensaError in promote halts the pipeline; embed never runs."""

    def _boom(
        *, recipes: object, extractions: object, version: str, dry_run: bool
    ) -> object:
        _ = recipes, extractions, version, dry_run
        calls.order.append("promote")
        msg = "promote blew up"
        raise ExtractionError(msg)

    monkeypatch.setattr("dispensa.app.promotion.promote_version", _boom)

    result = runner.invoke(cli.app, ["sync", "all", str(_food_json(tmp_path))])

    assert result.exit_code == 1
    assert calls.order == ["ingest", "extract", "promote"]
    assert "embed" not in calls.order
