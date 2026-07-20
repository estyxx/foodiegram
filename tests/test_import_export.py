import json
from pathlib import Path

from foodiegram.app.export import export_recipes
from foodiegram.app.import_json import import_recipes
from foodiegram.domain.models import Recipe
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.recipes_db import RecipeRepository
from foodiegram.storage.user_state_db import UserStateRepository

_EXPECTED_RECIPES = 2


def _recipe_json(
    code: str,
    *,
    is_favorite: bool | None = None,
    user_notes: str | None = None,
) -> str:
    """Build the JSON text of a minimal valid stored recipe."""
    payload: dict[str, object] = {
        "code": code,
        "pk": "1",
        "post_url": f"https://instagram.com/p/{code}/",
        "caption": None,
        "title": f"Recipe {code}",
        "ingredients": ["water"],
        "instructions": ["boil"],
    }
    if is_favorite is not None:
        payload["is_favorite"] = is_favorite
    if user_notes is not None:
        payload["user_notes"] = user_notes
    return json.dumps(payload)


def test_import_migrates_user_state_and_round_trips(tmp_path: Path) -> None:
    """Import loads recipes, migrates legacy favourite/notes, and exports cleanly."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "AAA.json").write_text(_recipe_json("AAA"), encoding="utf-8")
    (src / "BBB.json").write_text(
        _recipe_json("BBB", is_favorite=True, user_notes="yum"),
        encoding="utf-8",
    )

    engine = create_db_engine(f"sqlite:///{tmp_path}/db.sqlite")
    init_db(engine)
    recipes = RecipeRepository(engine)
    user_state = UserStateRepository(engine)

    stats = import_recipes(data_dir=src, recipes=recipes, user_state=user_state)

    assert stats.imported == _EXPECTED_RECIPES
    assert stats.favorites == 1
    assert stats.notes == 1
    assert stats.errors == 0

    favourite = user_state.get("BBB")
    assert favourite is not None
    assert favourite.is_favorite is True
    assert favourite.user_notes == "yum"
    assert user_state.all_favorites() == ["BBB"]

    out = tmp_path / "out"
    exported = export_recipes(recipes=recipes, out_dir=out)
    assert exported == _EXPECTED_RECIPES

    reimported = json.loads((out / "BBB.json").read_text(encoding="utf-8"))
    assert "is_favorite" not in reimported
    assert "user_notes" not in reimported
    assert Recipe.model_validate(reimported) == recipes.get("BBB")
