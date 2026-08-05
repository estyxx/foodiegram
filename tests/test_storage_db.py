from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import pytest
from sqlalchemy import Engine

from foodiegram.domain.enums import (
    Course,
    CuisineType,
    Difficulty,
    DishType,
    MealType,
    MedCategory,
    RecipeSource,
)
from foodiegram.domain.models import (
    CategoryServing,
    ExtractedRecipe,
    Extraction,
    Recipe,
)
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.recipes_db import RecipeRepository
from foodiegram.storage.user_state_db import UserStateRepository

_EXTRACTED_AT = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
_SECONDARY_SERVINGS = 0.5
_TWO_RECIPES = 2


@pytest.fixture
def engine(tmp_path: Path) -> Engine:
    """Create a fresh, initialised SQLite database in a temp directory."""
    eng = create_db_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(eng)
    return eng


def _full_recipe() -> Recipe:
    """Build a recipe exercising enums, JSON lists, and edited_fields."""
    return Recipe(
        code="ABC",
        source=RecipeSource.MANUAL,
        pk="42",
        post_url="https://instagram.com/p/ABC/",
        caption="Una caption verbatim 🍝",
        author_username="chef_test",
        title="Carbonara",
        ingredients=["guanciale", "uova", "pecorino"],
        instructions=["fry guanciale", "toss with eggs"],
        meal_type=MealType.LUNCH,
        dish_type=DishType.PASTA,
        cuisine_type=CuisineType.ITALIAN,
        difficulty=Difficulty.MEDIUM,
        course=Course.PRIMO,
        mediterranean_categories=[
            CategoryServing(category=MedCategory.EGGS),
            CategoryServing(
                category=MedCategory.PROCESSED_MEAT,
                servings=_SECONDARY_SERVINGS,
                source="manual",
            ),
        ],
        proteins=["uova"],
        vegetables=[],
        grains_starches=["pasta"],
        herbs_spices=["black pepper"],
        cooking_methods=["boiling", "frying"],
        equipment=["pot", "pan"],
        prep_time="10 minutes",
        cook_time="15 minutes",
        total_time="25 minutes",
        servings="2",
        base_servings=2,
        temperature="hot",
        texture=["creamy"],
        flavor_profile=["savory"],
        dietary_tags=["comfort"],
        health_tags=[],
        season=["year_round"],
        occasion=["weeknight"],
        skill_level="home",
        style_tags=["traditional"],
        prep_style=["quick"],
        cloudinary_url="https://cdn/cloud.jpg",
        thumbnail_url="https://cdn/thumb.jpg",
        edited_fields=frozenset({"ingredients", "title"}),
        archived=True,
        edited_by_user=True,
        is_recipe=True,
        confidence=0.95,
        extracted_at=_EXTRACTED_AT,
        model_used="gpt-5.4-mini-2026-03-17",
        prompt_version="2",
    )


def _payload() -> ExtractedRecipe:
    """Build a minimal valid extraction payload."""
    return ExtractedRecipe(
        title="Carbonara",
        ingredients=["guanciale"],
        instructions=["cook"],
        dish_type="pasta",
        meal_type="lunch",
        cuisine_type="italian",
        difficulty="easy",
        course="primo",
        mediterranean_categories=[],
        proteins=["uova"],
        vegetables=[],
        grains_starches=["pasta"],
        herbs_spices=[],
        cooking_methods=["boil"],
        equipment=["pot"],
        prep_time="10m",
        cook_time="15m",
        total_time="25m",
        servings="2",
        temperature="hot",
        texture=["creamy"],
        flavor_profile=["savory"],
        dietary_tags=[],
        health_tags=[],
        season=[],
        occasion=[],
        skill_level="home",
        style_tags=[],
        prep_style=[],
        is_recipe=True,
        confidence=0.9,
    )


def _extraction(
    *,
    prompt_version: str,
    kind: Literal["batch", "repair", "categories", "paste"] = "batch",
) -> Extraction:
    """Build an extraction for recipe ABC at a given prompt version."""
    return Extraction(
        id=None,
        recipe_code="ABC",
        prompt_version=prompt_version,
        model="gpt-5.4-mini-2026-03-17",
        batch_id=None,
        kind=kind,
        extracted_at=_EXTRACTED_AT,
        payload=_payload(),
    )


def test_recipe_round_trips_fully(engine: Engine) -> None:
    """A saved recipe reloads equal, with enums, JSON lists, and frozenset intact."""
    repo = RecipeRepository(engine)
    original = _full_recipe()

    repo.save(original)
    loaded = repo.get("ABC")

    assert loaded == original
    assert loaded is not None
    assert loaded.author_username == "chef_test"
    assert loaded.source is RecipeSource.MANUAL
    assert loaded.dish_type is DishType.PASTA
    assert isinstance(loaded.edited_fields, frozenset)
    assert loaded.edited_fields == {"ingredients", "title"}
    assert loaded.mediterranean_categories[1].category is MedCategory.PROCESSED_MEAT
    assert loaded.mediterranean_categories[1].servings == _SECONDARY_SERVINGS


def test_exists_and_list_all(engine: Engine) -> None:
    """Exists reflects presence; list_all returns saved recipes ordered by code."""
    repo = RecipeRepository(engine)
    assert repo.exists("ABC") is False

    repo.save(_full_recipe())

    assert repo.exists("ABC") is True
    assert [r.code for r in repo.list_all()] == ["ABC"]


def test_find_filters_on_is_recipe(engine: Engine) -> None:
    """is_recipe splits real recipes from inspiration saves; None keeps both."""
    repo = RecipeRepository(engine)
    repo.save(_full_recipe())
    repo.save(
        _full_recipe().model_copy(update={"code": "NOTR", "is_recipe": False}),
    )

    assert [r.code for r in repo.find(is_recipe=True)] == ["ABC"]
    assert [r.code for r in repo.find(is_recipe=False)] == ["NOTR"]
    assert [r.code for r in repo.find()] == ["ABC", "NOTR"]


def test_find_combines_is_recipe_with_other_filters(engine: Engine) -> None:
    """is_recipe narrows within another facet rather than replacing it."""
    repo = RecipeRepository(engine)
    repo.save(_full_recipe())
    repo.save(
        _full_recipe().model_copy(
            update={"code": "SOUP", "dish_type": DishType.SOUP, "is_recipe": False},
        ),
    )

    assert [r.code for r in repo.find(dish_type=DishType.SOUP, is_recipe=True)] == []
    assert [r.code for r in repo.find(dish_type=DishType.SOUP)] == ["SOUP"]


def _faceted(code: str, *, proteins: list[str], assigned: MedCategory | None) -> Recipe:
    """Build a recipe with the given protein words and one LLM category."""
    categories = [CategoryServing(category=assigned)] if assigned else []
    return _full_recipe().model_copy(
        update={
            "code": code,
            "proteins": proteins,
            "mediterranean_categories": categories,
        },
    )


def test_find_filters_on_protein_facet(engine: Engine) -> None:
    """A protein facet selects the recipes carrying that group."""
    repo = RecipeRepository(engine)
    repo.save(_faceted("FISH", proteins=["salmon"], assigned=MedCategory.FISH))
    repo.save(_faceted("BEEF", proteins=["beef"], assigned=MedCategory.RED_MEAT))
    repo.save(_faceted("NONE", proteins=[], assigned=None))

    matched = repo.find(protein_categories=[MedCategory.FISH])
    assert [r.code for r in matched] == ["FISH"]


def test_find_ors_several_protein_categories(engine: Engine) -> None:
    """Two facets OR together rather than intersecting."""
    repo = RecipeRepository(engine)
    repo.save(_faceted("FISH", proteins=["salmon"], assigned=MedCategory.FISH))
    repo.save(_faceted("BEEF", proteins=["beef"], assigned=MedCategory.RED_MEAT))
    repo.save(_faceted("TOFU", proteins=["tofu"], assigned=None))

    matched = repo.find(
        protein_categories=[MedCategory.FISH, MedCategory.RED_MEAT],
    )
    assert [r.code for r in matched] == ["BEEF", "FISH"]


def test_find_without_protein_categories_keeps_everything(engine: Engine) -> None:
    """None and an empty list both mean no protein filter."""
    repo = RecipeRepository(engine)
    repo.save(_faceted("FISH", proteins=["salmon"], assigned=MedCategory.FISH))
    repo.save(_faceted("NONE", proteins=[], assigned=None))

    assert len(repo.find()) == _TWO_RECIPES
    assert len(repo.find(protein_categories=[])) == _TWO_RECIPES


def test_protein_facet_follows_the_llm_except_for_plant(engine: Engine) -> None:
    """Animal facets come from the LLM; plant protein comes from the words."""
    repo = RecipeRepository(engine)
    # Cured meat the protein words miss entirely, but the LLM tagged.
    repo.save(_faceted("CURED", proteins=["pork"], assigned=MedCategory.PROCESSED_MEAT))
    # Tofu the LLM filed under legumes; the word list supplies plant protein.
    repo.save(_faceted("TOFU", proteins=["tofu"], assigned=MedCategory.LEGUMES))

    processed = repo.find(protein_categories=[MedCategory.PROCESSED_MEAT])
    assert [r.code for r in processed] == ["CURED"]

    plant = repo.find(protein_categories=[MedCategory.PLANT_PROTEIN])
    assert [r.code for r in plant] == ["TOFU"]

    # "pork" maps to red meat by word, but the LLM did not tag it as such.
    assert repo.find(protein_categories=[MedCategory.RED_MEAT]) == []


def test_extraction_append_and_latest_for(engine: Engine) -> None:
    """Extractions append with ids; latest_for returns the newest, version-aware."""
    RecipeRepository(engine).save(_full_recipe())
    repo = ExtractionRepository(engine)

    first = repo.add(_extraction(prompt_version="1"))
    second = repo.add(_extraction(prompt_version="2"))
    third = repo.add(_extraction(prompt_version="2", kind="repair"))

    assert first.id is not None
    assert second.id is not None
    assert third.id is not None

    latest = repo.latest_for("ABC")
    assert latest is not None
    assert latest.id == third.id

    latest_v1 = repo.latest_for("ABC", prompt_version="1")
    assert latest_v1 is not None
    assert latest_v1.id == first.id

    assert repo.list_versions("ABC") == ["1", "2"]
    assert [e.id for e in repo.for_version("2")] == [second.id, third.id]


def test_user_state_upsert(engine: Engine) -> None:
    """Favourite and notes upsert into one row; all_favorites lists the codes."""
    repo = UserStateRepository(engine)
    assert repo.get("ABC") is None

    repo.set_favorite("ABC", is_favorite=True)
    updated = repo.set_notes("ABC", notes="best carbonara")

    assert updated.is_favorite is True
    assert updated.user_notes == "best carbonara"

    stored = repo.get("ABC")
    assert stored is not None
    assert stored.is_favorite is True
    assert stored.user_notes == "best carbonara"

    repo.set_favorite("XYZ", is_favorite=True)
    assert repo.all_favorites() == ["ABC", "XYZ"]
