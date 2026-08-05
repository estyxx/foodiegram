from collections.abc import Sequence
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from foodiegram.api import create_app
from foodiegram.deps import AuthConfig, Deps
from foodiegram.domain.enums import MedCategory
from foodiegram.domain.models import CategoryServing, Recipe
from foodiegram.storage.extractions_db import ExtractionRepository
from foodiegram.storage.pantry_db import PantryRepository
from foodiegram.storage.plans_db import PlanRepository
from foodiegram.storage.recipes_db import RecipeRepository
from foodiegram.storage.targets_db import TargetRepository
from foodiegram.storage.user_state_db import UserStateRepository

_MONDAY = "2024-01-01"
_TUESDAY = "2024-01-02"
_SEEDED_TARGETS = 7
_TWO_SERVINGS = 2.0
_UPDATED_MIN = 3.0
_UPDATED_SERVINGS = 4


def _fish_recipe(code: str, *, confidence: float = 0.8) -> Recipe:
    """Build a minimal one-serving fish recipe."""
    return Recipe(
        code=code,
        pk="1",
        post_url=f"https://instagram.com/p/{code}/",
        caption=None,
        title=f"Recipe {code}",
        ingredients=["200g salmon", "2 eggs"],
        instructions=["cook"],
        mediterranean_categories=[CategoryServing(category=MedCategory.FISH)],
        confidence=confidence,
    )


def _inspiration_recipe(code: str) -> Recipe:
    """Build a saved post the extractor judged not to be a recipe."""
    return _fish_recipe(code).model_copy(update={"is_recipe": False})


def _make_deps(engine: Engine) -> Deps:
    return Deps(
        recipes=RecipeRepository(engine),
        extractions=ExtractionRepository(engine),
        user_state=UserStateRepository(engine),
        plans=PlanRepository(engine),
        pantry=PantryRepository(engine),
        targets=TargetRepository(engine),
    )


@pytest.fixture
def deps(db_engine: Engine) -> Deps:
    """Repositories wired to the temp SQLite engine."""
    return _make_deps(db_engine)


@pytest.fixture
def client(deps: Deps) -> TestClient:
    """Return a TestClient over an auth-disabled app."""
    return TestClient(create_app(deps=deps))


def _fish_category(body: dict[str, object]) -> dict[str, object]:
    balance = body["balance"]
    assert isinstance(balance, list)
    return next(s for s in balance if s["category"] == MedCategory.FISH.value)


def test_get_plan_returns_balance_and_suggestions(
    client: TestClient,
    deps: Deps,
) -> None:
    """An empty plan reports every target and suggests recipes for the gaps."""
    deps.recipes.save(_fish_recipe("F1"))

    response = client.get(f"/api/plans/{_MONDAY}")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["week_start"] == _MONDAY
    assert body["meals"] == []
    assert len(body["balance"]) == _SEEDED_TARGETS
    assert _fish_category(body)["state"] == "under"

    fish_gap = next(
        gap for gap in body["suggestions"] if gap["category"] == MedCategory.FISH.value
    )
    assert [recipe["code"] for recipe in fish_gap["recipes"]] == ["F1"]


def test_non_monday_week_start_is_rejected(client: TestClient) -> None:
    """A non-Monday week_start returns 422."""
    assert client.get(f"/api/plans/{_TUESDAY}").status_code == (
        HTTPStatus.UNPROCESSABLE_ENTITY
    )


def test_upsert_meal_is_idempotent_and_moves_the_balance(
    client: TestClient,
    deps: Deps,
) -> None:
    """Upserting the same slot replaces it; two fish slots reach the target."""
    deps.recipes.save(_fish_recipe("F1"))
    deps.recipes.save(_fish_recipe("F2"))

    first = client.put(
        f"/api/plans/{_MONDAY}/meals",
        json={"day": _MONDAY, "meal": "lunch", "recipe_code": "F1"},
    )
    assert first.status_code == HTTPStatus.OK

    # Re-PUT the same (day, slot) with a different recipe → replace, not append.
    replaced = client.put(
        f"/api/plans/{_MONDAY}/meals",
        json={"day": _MONDAY, "meal": "lunch", "recipe_code": "F2"},
    )
    assert len(replaced.json()["meals"]) == 1

    client.put(
        f"/api/plans/{_MONDAY}/meals",
        json={"day": _MONDAY, "meal": "dinner", "recipe_code": "F1"},
    )

    body = client.get(f"/api/plans/{_MONDAY}").json()
    assert len(body["meals"]) == _TWO_SERVINGS
    assert _fish_category(body)["planned"] == _TWO_SERVINGS
    assert _fish_category(body)["state"] == "ok"


def test_delete_meal(client: TestClient, deps: Deps) -> None:
    """A meal can be deleted by id; deleting a missing id is 404."""
    deps.recipes.save(_fish_recipe("F1"))
    created = client.put(
        f"/api/plans/{_MONDAY}/meals",
        json={"day": _MONDAY, "meal": "lunch", "recipe_code": "F1"},
    ).json()
    meal_id = created["meals"][0]["id"]

    deleted = client.delete(f"/api/plans/{_MONDAY}/meals/{meal_id}")
    assert deleted.status_code == HTTPStatus.OK
    assert deleted.json()["meals"] == []

    missing = client.delete(f"/api/plans/{_MONDAY}/meals/{meal_id}")
    assert missing.status_code == HTTPStatus.NOT_FOUND


def test_pantry_crud(client: TestClient) -> None:
    """Pantry items can be created, listed, and deleted."""
    created = client.post(
        "/api/pantry",
        json={"name": "olive oil", "kind": "staple"},
    )
    assert created.status_code == HTTPStatus.CREATED
    item_id = created.json()["id"]

    listed = client.get("/api/pantry").json()
    assert [item["name"] for item in listed] == ["olive oil"]

    assert client.delete(f"/api/pantry/{item_id}").status_code == (HTTPStatus.NO_CONTENT)
    assert client.get("/api/pantry").json() == []
    assert client.delete(f"/api/pantry/{item_id}").status_code == HTTPStatus.NOT_FOUND


def test_targets_seeded_and_updatable(client: TestClient) -> None:
    """Targets are seeded on init and updatable via PUT."""
    seeded = client.get("/api/targets").json()
    assert len(seeded) == _SEEDED_TARGETS

    updated = client.put(
        "/api/targets",
        json={
            "targets": [
                {
                    "category": MedCategory.FISH.value,
                    "min_servings": 3,
                    "max_servings": 4,
                },
            ],
        },
    )
    assert updated.status_code == HTTPStatus.OK
    fish = next(t for t in updated.json() if t["category"] == MedCategory.FISH.value)
    assert fish["min_servings"] == _UPDATED_MIN


def test_targets_reject_unknown_category(client: TestClient) -> None:
    """An unknown target category is rejected with 422."""
    response = client.put(
        "/api/targets",
        json={"targets": [{"category": "nope", "min_servings": 1, "max_servings": 2}]},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_shopping_list_lists_missing_ingredients(
    client: TestClient,
    deps: Deps,
) -> None:
    """Planned ingredients not in the pantry appear in the shopping list."""
    deps.recipes.save(_fish_recipe("F1"))
    client.put(
        f"/api/plans/{_MONDAY}/meals",
        json={"day": _MONDAY, "meal": "lunch", "recipe_code": "F1"},
    )

    groups = client.get(f"/api/plans/{_MONDAY}/shopping-list").json()
    names = {item["name"] for group in groups for item in group["items"]}
    assert "salmon" in names


def test_favourite_and_notes_round_trip(client: TestClient, deps: Deps) -> None:
    """PATCH persists favourite/notes to user_state and reads them back."""
    deps.recipes.save(_fish_recipe("F1"))

    patched = client.patch(
        "/api/recipes/F1",
        json={"is_favorite": True, "user_notes": "weeknight winner"},
    )
    assert patched.status_code == HTTPStatus.OK
    assert patched.json()["is_favorite"] is True
    assert patched.json()["user_notes"] == "weeknight winner"

    detail = client.get("/api/recipes/F1").json()
    assert detail["is_favorite"] is True
    assert detail["user_notes"] == "weeknight winner"

    only_favs = client.get("/api/recipes", params={"is_favorite": "true"}).json()
    assert [r["code"] for r in only_favs] == ["F1"]
    assert only_favs[0]["is_favorite"] is True

    client.patch("/api/recipes/F1", json={"is_favorite": False})
    assert client.get("/api/recipes", params={"is_favorite": "true"}).json() == []


def test_patch_base_servings_marks_recipe_edited(
    client: TestClient,
    deps: Deps,
) -> None:
    """A recipe-field PATCH persists and flags the recipe as user-edited."""
    deps.recipes.save(_fish_recipe("F1"))

    patched = client.patch("/api/recipes/F1", json={"base_servings": 4})
    assert patched.status_code == HTTPStatus.OK

    detail = client.get("/api/recipes/F1").json()
    assert detail["base_servings"] == _UPDATED_SERVINGS
    assert detail["edited_by_user"] is True


def test_list_recipes_filters_on_is_recipe(client: TestClient, deps: Deps) -> None:
    """The is_recipe parameter selects a segment; omitting it returns both."""
    deps.recipes.save(_fish_recipe("F1"))
    deps.recipes.save(_inspiration_recipe("N1"))

    only_recipes = client.get("/api/recipes", params={"is_recipe": "true"}).json()
    assert [r["code"] for r in only_recipes] == ["F1"]

    only_saves = client.get("/api/recipes", params={"is_recipe": "false"}).json()
    assert [r["code"] for r in only_saves] == ["N1"]

    everything = client.get("/api/recipes").json()
    assert {r["code"] for r in everything} == {"F1", "N1"}


def test_recipe_counts_report_both_segments(client: TestClient, deps: Deps) -> None:
    """The count endpoint returns each segment total under the active facets."""
    deps.recipes.save(_fish_recipe("F1"))
    deps.recipes.save(_fish_recipe("F2"))
    deps.recipes.save(_inspiration_recipe("N1"))

    body = client.get("/api/recipes/count").json()
    assert body == {"recipes_only": 2, "all_saves": 3}

    # A facet shared with /recipes narrows both totals the same way.
    client.patch("/api/recipes/F1", json={"is_favorite": True})
    favourites_only = client.get(
        "/api/recipes/count",
        params={"is_favorite": "true"},
    ).json()
    assert favourites_only == {"recipes_only": 1, "all_saves": 1}


def _protein_recipe(
    code: str,
    *,
    proteins: list[str],
    assigned: MedCategory | None,
) -> Recipe:
    """Build a recipe with the given protein words and one LLM category."""
    categories = [CategoryServing(category=assigned)] if assigned else []
    return _fish_recipe(code).model_copy(
        update={"proteins": proteins, "mediterranean_categories": categories},
    )


def test_protein_category_facet_filters_and_ors(client: TestClient, deps: Deps) -> None:
    """A protein facet selects its group; repeating the parameter ORs the groups."""
    deps.recipes.save(_protein_recipe("TOFU", proteins=["tofu"], assigned=None))
    deps.recipes.save(
        _protein_recipe("SALM", proteins=["salmon"], assigned=MedCategory.FISH),
    )
    deps.recipes.save(
        _protein_recipe("BEEF", proteins=["beef"], assigned=MedCategory.RED_MEAT),
    )

    plant = client.get("/api/recipes", params={"protein_category": "plant_protein"})
    assert [r["code"] for r in plant.json()] == ["TOFU"]

    both = client.get(
        "/api/recipes",
        params=[("protein_category", "plant_protein"), ("protein_category", "fish")],
    )
    assert [r["code"] for r in both.json()] == ["SALM", "TOFU"]


def test_unknown_protein_category_is_ignored(client: TestClient, deps: Deps) -> None:
    """An invalid facet value is dropped rather than raising a 500."""
    deps.recipes.save(_protein_recipe("TOFU", proteins=["tofu"], assigned=None))

    response = client.get("/api/recipes", params={"protein_category": "unicorn"})
    assert response.status_code == HTTPStatus.OK
    assert [r["code"] for r in response.json()] == ["TOFU"]

    # A valid value alongside an invalid one still filters on the valid one.
    mixed = client.get(
        "/api/recipes",
        params=[("protein_category", "unicorn"), ("protein_category", "fish")],
    )
    assert mixed.json() == []


def test_processed_meat_facet_reads_the_llm_tag(client: TestClient, deps: Deps) -> None:
    """Cured meat has no protein word, so the facet relies on the LLM category."""
    deps.recipes.save(
        _protein_recipe("CURED", proteins=["pork"], assigned=MedCategory.PROCESSED_MEAT),
    )
    deps.recipes.save(
        _protein_recipe("ROAST", proteins=["pork"], assigned=MedCategory.RED_MEAT),
    )

    response = client.get("/api/recipes", params={"protein_category": "processed_meat"})

    assert [r["code"] for r in response.json()] == ["CURED"]


def test_recipe_counts_respect_the_protein_facet(client: TestClient, deps: Deps) -> None:
    """The count endpoint narrows by the same facet the list uses."""
    deps.recipes.save(_protein_recipe("TOFU", proteins=["tofu"], assigned=None))
    deps.recipes.save(
        _protein_recipe("SALM", proteins=["salmon"], assigned=MedCategory.FISH),
    )
    deps.recipes.save(
        _protein_recipe("NOTR", proteins=["tofu"], assigned=None).model_copy(
            update={"is_recipe": False},
        ),
    )

    body = client.get(
        "/api/recipes/count",
        params={"protein_category": "plant_protein"},
    ).json()

    assert body == {"recipes_only": 1, "all_saves": 2}


def _ingredient_recipe(code: str, ingredients: list[str]) -> Recipe:
    """Build a recipe carrying the given ingredient lines."""
    return _fish_recipe(code).model_copy(update={"ingredients": ingredients})


def test_ingredient_chips_and_together(client: TestClient, deps: Deps) -> None:
    """Repeating ingredient requires every term, and expands through synonyms."""
    deps.recipes.save(_ingredient_recipe("BOTH", ["300g zucca", "200g tofu"]))
    deps.recipes.save(_ingredient_recipe("PUMP", ["pumpkin puree", "tofu"]))
    deps.recipes.save(_ingredient_recipe("ONE", ["300g zucca"]))

    response = client.get(
        "/api/recipes",
        params=[("ingredient", "zucca"), ("ingredient", "tofu")],
    )

    assert [r["code"] for r in response.json()] == ["BOTH", "PUMP"]


def test_blank_ingredient_values_are_ignored(client: TestClient, deps: Deps) -> None:
    """An empty chip does not collapse the result set."""
    deps.recipes.save(_ingredient_recipe("ONE", ["300g zucca"]))

    response = client.get("/api/recipes", params={"ingredient": "  "})

    assert response.status_code == HTTPStatus.OK
    assert [r["code"] for r in response.json()] == ["ONE"]


def test_recipe_counts_respect_ingredient_chips(client: TestClient, deps: Deps) -> None:
    """The count endpoint narrows by the chips too, so "Show N" tracks them."""
    deps.recipes.save(_ingredient_recipe("BOTH", ["zucca", "tofu"]))
    deps.recipes.save(_ingredient_recipe("ONE", ["zucca"]))

    body = client.get(
        "/api/recipes/count",
        params=[("ingredient", "zucca"), ("ingredient", "tofu")],
    ).json()

    assert body == {"recipes_only": 1, "all_saves": 1}


def test_recipe_count_route_is_not_read_as_a_code(client: TestClient) -> None:
    """/recipes/count resolves to the count endpoint, not the detail route."""
    response = client.get("/api/recipes/count")

    assert response.status_code == HTTPStatus.OK
    assert "recipes_only" in response.json()


def _credentialed_client(engine: Engine, creds: Sequence[str]) -> TestClient:
    deps = _make_deps(engine)
    app = create_app(deps=deps, auth=AuthConfig(username=creds[0], password=creds[1]))
    return TestClient(app)


def test_basic_auth_blocks_and_allows(db_engine: Engine) -> None:
    """With auth enabled, missing creds get 401 and correct creds pass."""
    client = _credentialed_client(db_engine, ("user", "pass"))

    unauthorized = client.get("/api/targets")
    assert unauthorized.status_code == HTTPStatus.UNAUTHORIZED
    assert unauthorized.headers["WWW-Authenticate"] == 'Basic realm="dispensa"'

    ok = client.get("/api/targets", auth=("user", "pass"))
    assert ok.status_code == HTTPStatus.OK

    wrong = client.get("/api/targets", auth=("user", "nope"))
    assert wrong.status_code == HTTPStatus.UNAUTHORIZED


def test_recipe_detail_includes_author(client: TestClient, deps: Deps) -> None:
    """The detail response exposes the post author's Instagram handle."""
    deps.recipes.save(
        _fish_recipe("F1").model_copy(update={"author_username": "chef_ig"}),
    )

    body = client.get("/api/recipes/F1").json()

    assert body["author_username"] == "chef_ig"


def test_version_endpoint_reports_build(client: TestClient) -> None:
    """The version endpoint returns a package version and a commit field."""
    body = client.get("/api/version").json()

    assert body["version"]
    assert "commit" in body


def test_serves_spa_from_configured_frontend_dir(
    deps: Deps,
    tmp_path: Path,
) -> None:
    """The SPA is served from the injected frontend_dir, not a fixed path."""
    (tmp_path / "index.html").write_text("<h1>hi</h1>", encoding="utf-8")
    client = TestClient(create_app(deps=deps, frontend_dir=tmp_path))

    response = client.get("/")

    assert response.status_code == HTTPStatus.OK
    assert "<h1>hi</h1>" in response.text
