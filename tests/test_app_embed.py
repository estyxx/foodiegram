from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from sqlalchemy import Engine

from foodiegram.ai.embeddings import recipe_document
from foodiegram.app.embed import embed_recipes
from foodiegram.domain.hashing import document_hash
from foodiegram.domain.models import Recipe
from foodiegram.storage.recipes_db import RecipeRepository

if TYPE_CHECKING:
    from openai import OpenAI

_MODEL = "text-embedding-3-small"
_STALE_PLUS_MISSING = 2


@dataclass
class _FakeItem:
    index: int
    embedding: list[float]


@dataclass
class _FakeResponse:
    data: list[_FakeItem]


@dataclass
class _FakeEmbeddings:
    calls: list[list[str]] = field(default_factory=list)

    def create(
        self,
        *,
        input: list[str],  # noqa: A002
        model: str,
    ) -> _FakeResponse:
        """Record the batch and return one vector per input, in order."""
        _ = model
        self.calls.append(input)
        return _FakeResponse(
            data=[
                _FakeItem(index=index, embedding=[float(index), 0.0, 0.0])
                for index, _text in enumerate(input)
            ],
        )


@dataclass
class _FakeOpenAI:
    embeddings: _FakeEmbeddings = field(default_factory=_FakeEmbeddings)


def _recipe(code: str) -> Recipe:
    """Build a minimal recipe with a non-empty embedding document."""
    return Recipe(
        code=code,
        pk="1",
        post_url=None,
        caption=None,
        title=f"Recipe {code}",
        ingredients=["water"],
        instructions=["boil"],
    )


def test_embed_changed_reembeds_stale_and_missing_skips_fresh(engine: Engine) -> None:
    """Stale and embedding-less recipes are embedded; up-to-date ones are skipped."""
    repo = RecipeRepository(engine)
    stale = _recipe("STALE")
    fresh = _recipe("FRESH")
    missing = _recipe("MISSING")
    for recipe in (stale, fresh, missing):
        repo.save(recipe)
    repo.save_embedding("STALE", [9.0, 9.0, 9.0], model=_MODEL, source_hash="outdated")
    repo.save_embedding(
        "FRESH",
        [1.0, 0.0, 0.0],
        model=_MODEL,
        source_hash=document_hash(recipe_document(fresh)),
    )
    fake = _FakeOpenAI()

    report = embed_recipes(recipes=repo, client=cast("OpenAI", fake))

    assert report.needs_embedding == _STALE_PLUS_MISSING
    assert report.embedded == _STALE_PLUS_MISSING
    assert report.skipped_up_to_date == 1
    assert len(fake.embeddings.calls) == 1
    assert set(fake.embeddings.calls[0]) == {
        recipe_document(stale),
        recipe_document(missing),
    }


def test_embed_all_fresh_calls_no_client(engine: Engine) -> None:
    """When every embedding is current, nothing is embedded and no call is made."""
    repo = RecipeRepository(engine)
    recipe = _recipe("FRESH")
    repo.save(recipe)
    repo.save_embedding(
        "FRESH",
        [1.0, 0.0, 0.0],
        model=_MODEL,
        source_hash=document_hash(recipe_document(recipe)),
    )
    fake = _FakeOpenAI()

    report = embed_recipes(recipes=repo, client=cast("OpenAI", fake))

    assert report.needs_embedding == 0
    assert report.embedded == 0
    assert report.skipped_up_to_date == 1
    assert fake.embeddings.calls == []


def test_embed_dry_run_reports_without_writing(engine: Engine) -> None:
    """Dry-run counts the stale recipe but writes nothing and calls no client."""
    repo = RecipeRepository(engine)
    recipe = _recipe("STALE")
    repo.save(recipe)
    repo.save_embedding("STALE", [9.0, 9.0, 9.0], model=_MODEL, source_hash="outdated")
    fake = _FakeOpenAI()

    report = embed_recipes(recipes=repo, client=cast("OpenAI", fake), dry_run=True)

    assert report.needs_embedding == 1
    assert report.embedded == 0
    assert fake.embeddings.calls == []
    assert repo.embedding_source_hashes()["STALE"] == "outdated"
