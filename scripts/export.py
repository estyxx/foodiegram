"""Export the database to one JSON file per recipe (sorted keys, stable diffs).

Honours DATABASE_URL (default sqlite:///data/dispensa.db). Run after each
batch/edit session and commit the output in the private data repo. Run via:
uv run scripts/export.py [--out data/recipes]
"""

import argparse
import logging
from pathlib import Path

from foodiegram.app.export import export_recipes
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine, init_db
from foodiegram.storage.recipes_db import RecipeRepository


def main() -> None:
    """Export every recipe in the database to a directory of JSON files."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Export database recipes to JSON files.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="DIR",
        help="Output directory (default: settings.data_dir)",
    )
    args = parser.parse_args()

    settings = Settings()
    out_dir: Path = args.out or settings.data_dir

    engine = create_db_engine(settings.database_url)
    init_db(engine)

    count = export_recipes(recipes=RecipeRepository(engine), out_dir=out_dir)
    print(f"Exported {count} recipes to {out_dir}")


if __name__ == "__main__":
    main()
