r"""Probe semantic search against the local database.

Run via:

    uv run python scripts/probe_semantic_search.py "dolce per colazione con proteine"
    uv run python scripts/probe_semantic_search.py "dolce per colazione con proteine" \\
        --proteins eggs
"""

import argparse
import logging

from openai import OpenAI

from foodiegram.app.search_recipes import search_recipes_semantic
from foodiegram.settings import Settings
from foodiegram.storage.db import create_db_engine
from foodiegram.storage.recipes_db import RecipeRepository

logger = logging.getLogger(__name__)


def main() -> None:
    """Run one semantic search query and print ranked hits."""
    parser = argparse.ArgumentParser(description="Probe semantic recipe search.")
    parser.add_argument("query", help="Free-text search query to embed.")
    parser.add_argument(
        "--limit",
        type=int,
        default=8,
        metavar="N",
        help="Maximum number of results (default: 8).",
    )
    parser.add_argument(
        "--proteins",
        nargs="*",
        default=None,
        metavar="PROTEIN",
        help="Optional protein filter (ANY-match, synonym-expanded).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    settings = Settings()
    engine = create_db_engine(settings.database_url)
    repo = RecipeRepository(engine)
    client = OpenAI(api_key=settings.require_openai_api_key())

    results = search_recipes_semantic(
        recipes=repo,
        client=client,
        query=args.query,
        proteins=args.proteins,
        is_recipe=True,
        limit=args.limit,
    )

    print(f"query={args.query!r}  hits={len(results)}")
    for recipe, score in results:
        proteins = " ".join(recipe.proteins)
        title = recipe.title or ""
        dish = recipe.dish_type.value
        meal = recipe.meal_type.value
        print(
            f"{score:.3f}  {recipe.code:<12}  {dish}/{meal:<10}  {proteins}  {title}",
        )


if __name__ == "__main__":
    main()
