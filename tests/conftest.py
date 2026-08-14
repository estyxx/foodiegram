from collections.abc import Callable, Generator, Sequence
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine
from sqlmodel import SQLModel

from foodiegram.domain.models import (
    ExtractedCategoryServing,
    ExtractedRecipe,
    Extraction,
)
from foodiegram.settings import Settings
from foodiegram.storage.db import (
    _seed_targets,
    create_db_engine,
    truncate_all_tables,
)
from foodiegram.storage.maintenance import ensure_database

_FIXTURE_AT = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


def _test_database_url() -> str:
    """Return the Postgres test URL without reading a local .env override."""
    return Settings(_env_file=None).database_url_test


def _sample_extracted(
    *,
    title: str = "Sample",
    dish_type: str = "pasta",
    meal_type: str = "lunch",
    ingredients: Sequence[str] = ("water",),
    instructions: Sequence[str] = ("boil",),
    categories: Sequence[str] = ("eggs",),
) -> ExtractedRecipe:
    """Build a fully valid ExtractedRecipe with a few overridable fields."""
    return ExtractedRecipe(
        title=title,
        ingredients=list(ingredients),
        instructions=list(instructions),
        dish_type=dish_type,
        meal_type=meal_type,
        cuisine_type="italian",
        difficulty="easy",
        course="primo",
        mediterranean_categories=[
            ExtractedCategoryServing(category=category) for category in categories
        ],
        proteins=["eggs"],
        vegetables=[],
        grains_starches=["pasta"],
        herbs_spices=[],
        cooking_methods=["boiling"],
        equipment=["pot"],
        prep_time="10 minutes",
        cook_time="15 minutes",
        total_time="25 minutes",
        servings="2",
        temperature="hot",
        texture=["creamy"],
        flavor_profile=["savory"],
        dietary_tags=[],
        health_tags=[],
        season=["year_round"],
        occasion=["weeknight"],
        skill_level="beginner",
        style_tags=["home_cooking"],
        prep_style=["quick"],
        is_recipe=True,
        confidence=0.9,
    )


def _sample_extraction(
    *,
    code: str,
    payload: ExtractedRecipe,
    version: str = "2",
    batch_id: str | None = "b1",
) -> Extraction:
    """Build an append-only Extraction wrapping payload for code."""
    return Extraction(
        id=None,
        recipe_code=code,
        prompt_version=version,
        model="gpt-test",
        batch_id=batch_id,
        kind="batch",
        extracted_at=_FIXTURE_AT,
        payload=payload,
    )


@pytest.fixture
def make_extracted() -> Callable[..., ExtractedRecipe]:
    """Return a factory that builds valid ExtractedRecipe payloads."""
    return _sample_extracted


@pytest.fixture
def make_extraction() -> Callable[..., Extraction]:
    """Return a factory that builds Extraction rows around a payload."""
    return _sample_extraction


@pytest.fixture(scope="session")
def postgres_engine() -> Generator[Engine]:
    """Return a session-scoped engine bound to DATABASE_URL_TEST only."""
    test_url = _test_database_url()
    ensure_database(database_url=test_url)
    engine = create_db_engine(test_url)
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_engine(postgres_engine: Engine) -> Generator[Engine]:
    """Return a clean Postgres test database for one test function."""
    truncate_all_tables(postgres_engine)
    _seed_targets(postgres_engine)
    return postgres_engine


@pytest.fixture
def engine(db_engine: Engine) -> Engine:
    """Alias for storage tests that expect an engine fixture."""
    return db_engine
