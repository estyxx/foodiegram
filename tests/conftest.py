from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from foodiegram.domain.models import (
    ExtractedCategoryServing,
    ExtractedRecipe,
    Extraction,
)
from foodiegram.storage.db import create_db_engine, init_db

_FIXTURE_AT = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)


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


@pytest.fixture
def db_engine(tmp_path: Path) -> Engine:
    """Return an initialised SQLite engine backed by a temp file."""
    engine = create_db_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    return engine
