.PHONY: serve-api import lint test

serve-api:
	uv run uvicorn foodiegram.api:app --reload --port 8000

import:
	uv run python scripts/import_existing.py

lint:
	uv run ruff check src/ scripts/ && uv run mypy --strict src/

test:
	uv run pytest tests/
