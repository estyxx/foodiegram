---
name: green
description: Run the full green gate and fix failures until clean
user-invocable: true
---
Run these in order, fixing failures until all pass. Do not skip a step:
1. uv run ruff check --fix .
2. uv run ruff format .
3. uv run mypy src
4. uv run pytest -q
5. uv run lint-imports
Report the final result of each.
