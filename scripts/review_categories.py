"""Interactive review of Mediterranean categories using a pydantic-ai agent.

Select recipes needing category review, propose categories per recipe via the
categories-only agent, and prompt y/n/skip on stdin. Accepted proposals are
written with source="manual" and mark the recipe edited_by_user.
"""

import argparse
import logging
from typing import TYPE_CHECKING

from foodiegram.ai.repair import (
    build_category_agent,
    load_processed_meat_keywords,
    propose_categories,
)
from foodiegram.app.review_categories import (
    apply_reviewed_categories,
    select_for_review,
)
from foodiegram.settings import Settings
from foodiegram.storage.recipes_json import RecipeRepository

if TYPE_CHECKING:
    from collections.abc import Sequence

    from foodiegram.domain.models import CategoryServing, ExtractedCategoryServing

logger = logging.getLogger(__name__)


def _format_current(categories: Sequence[CategoryServing]) -> str:
    """Render the recipe's current categories for display."""
    if not categories:
        return "(none)"
    return ", ".join(
        f"{serving.category.value} x{serving.servings}"
        f"{' oily' if serving.is_oily_fish else ''}"
        for serving in categories
    )


def _format_proposed(categories: Sequence[ExtractedCategoryServing]) -> str:
    """Render the agent's proposed categories for display."""
    if not categories:
        return "(none)"
    return ", ".join(
        f"{serving.category} x{serving.servings}"
        f"{' oily' if serving.is_oily_fish else ''}"
        for serving in categories
    )


def main() -> None:
    """Run the interactive category-review loop."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Interactively review Mediterranean categories.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Max recipes to review")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Propose changes without writing them",
    )
    args = parser.parse_args()

    settings = Settings()
    repo = RecipeRepository(settings.data_dir)
    keywords = load_processed_meat_keywords()
    agent = build_category_agent(api_key=settings.openai_api_key)

    candidates = select_for_review(
        repo.list_all(),
        processed_meat_keywords=keywords,
        limit=args.limit,
    )
    logger.info("Selected %d recipe(s) for review", len(candidates))

    for recipe in candidates:
        logger.info("")
        logger.info("── %s (%s)", recipe.title, recipe.code)
        logger.info("current:  %s", _format_current(recipe.mediterranean_categories))

        if not recipe.caption:
            logger.info("no caption — skipping")
            continue

        proposed = propose_categories(agent, recipe.caption)
        logger.info("proposed: %s", _format_proposed(proposed))

        if input("accept? [y/n/skip] ").strip().lower() != "y":
            logger.info("skipped")
            continue

        updated = apply_reviewed_categories(recipe, proposed)
        if args.dry_run:
            logger.info("dry-run: would save %s", recipe.code)
            continue
        repo.save(updated)
        logger.info("saved %s", recipe.code)


if __name__ == "__main__":
    main()
