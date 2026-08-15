r"""Probe MCP get_recipe against the local database.

Run via:

    uv run python scripts/probe_get_recipe.py CTorNw0Aw6-
    uv run python scripts/probe_get_recipe.py ABC
"""

import argparse
import logging

from foodiegram.mcp_server.server import get_recipe

logger = logging.getLogger(__name__)


def main() -> None:
    """Fetch one recipe by code and print ingredients and instructions."""
    parser = argparse.ArgumentParser(description="Probe MCP get_recipe output.")
    parser.add_argument("code", help="Recipe code to fetch.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    result = get_recipe(code=args.code)
    if result is None:
        print(f"code={args.code!r}  not found")
        return

    ingredients = result.get("ingredients", [])
    instructions = result.get("instructions", [])
    print(f"code={args.code!r}  title={result.get('title')!r}")
    print(f"ingredients ({len(ingredients)}):")
    for line in ingredients:
        print(f"  - {line}")
    print(f"instructions ({len(instructions)}):")
    for step in instructions:
        print(f"  - {step}")
    if not ingredients and not instructions:
        print(
            "No ingredients or instructions in the DB for this code — "
            "re-extraction may be needed.",
        )


if __name__ == "__main__":
    main()
