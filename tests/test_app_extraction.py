from pathlib import Path

import pytest
from sqlalchemy import Engine

from foodiegram.app import extraction
from foodiegram.domain.models import Recipe
from foodiegram.settings import Settings
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.recipes_db import RecipeRepository

_CAPTION = "x" * 100
_SUBMIT_LIMIT = 2


def _recipe(code: str) -> Recipe:
    """Build a minimal recipe with a long-enough caption to be extraction-eligible."""
    return Recipe(
        code=code,
        pk="1",
        post_url=None,
        caption=_CAPTION,
        title=f"Recipe {code}",
        ingredients=["water"],
        instructions=["boil"],
    )


def test_submit_batch_advances_past_recipes_from_a_prior_unapplied_batch(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second --limit call skips codes already sent in a batch, even unapplied.

    Simulates the real workflow: `sync extract --limit 2` twice in a row before
    the first batch has completed/been applied. Without excluding
    already-submitted codes, both calls would resubmit the same first 2 recipes.
    """
    recipes = RecipeRepository(engine)
    extractions = ExtractionRepository(engine)
    for code in ("AAA", "BBB", "CCC"):
        recipes.save(_recipe(code))

    submitted: list[list[str]] = []

    def _fake_write_batch_input(batch_recipes: list[Recipe]) -> Path:
        submitted.append([r.code for r in batch_recipes])
        return Path("unused.jsonl")

    def _fake_create_batch(_settings: Settings, *, input_path: Path) -> str:
        _ = input_path
        return "b1"

    monkeypatch.setattr(extraction, "write_batch_input", _fake_write_batch_input)
    monkeypatch.setattr(extraction, "create_batch", _fake_create_batch)

    settings = Settings(openai_api_key="test-key")
    already_submitted: set[str] = set()
    monkeypatch.setattr(extraction, "submitted_codes", lambda: already_submitted)

    first_count = extraction.submit_batch(
        settings, recipes=recipes, extractions=extractions, limit=_SUBMIT_LIMIT
    )
    assert first_count == _SUBMIT_LIMIT
    assert submitted[-1] == ["AAA", "BBB"]

    already_submitted |= {"AAA", "BBB"}

    second_count = extraction.submit_batch(
        settings, recipes=recipes, extractions=extractions, limit=_SUBMIT_LIMIT
    )
    assert second_count == 1
    assert submitted[-1] == ["CCC"]
