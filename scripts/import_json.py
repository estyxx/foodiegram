"""Load recipe JSON files into the database (initial load / disaster recovery).

Honours DATABASE_URL (default sqlite:///data/dispensa.db). Run via:
uv run scripts/import_json.py [--data-dir data/recipes]
"""

import argparse
import logging
from pathlib import Path

from foodiegram.app.import_json import import_recipes
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.recipes_db import RecipeRepository
from foodiegram.storage.user_state_db import UserStateRepository


def main() -> None:
    """Import recipes from a directory of JSON files into the database."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Import recipe JSON files into the database.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory of recipe JSON files (default: settings.data_dir)",
    )
    args = parser.parse_args()

    settings = Settings()
    data_dir: Path = args.data_dir or settings.data_dir

    engine = create_db_engine(settings.database_url)
    init_db(engine)

    stats = import_recipes(
        data_dir=data_dir,
        recipes=RecipeRepository(engine),
        user_state=UserStateRepository(engine),
    )

    print(
        f"Imported {stats.imported} recipes "
        f"({stats.favorites} favourites, {stats.notes} notes), "
        f"{stats.errors} errors",
    )


if __name__ == "__main__":
    main()
