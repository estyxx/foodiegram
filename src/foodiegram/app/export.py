import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from foodiegram.storage.recipes_db import RecipeRepository


def export_recipes(*, recipes: RecipeRepository, out_dir: Path) -> int:
    """Write every recipe to out_dir as one sorted-key JSON file; return the count.

    Sorted keys keep git diffs of the exported data stable across runs.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for recipe in recipes.list_all():
        payload = recipe.model_dump(mode="json")
        text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        (out_dir / f"{recipe.code}.json").write_text(text + "\n", encoding="utf-8")
        count += 1
    return count
