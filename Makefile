.PHONY: ingest submit submit-force status apply serve-api lint test

# ── Pipeline ──────────────────────────────────────────────────────────────────

# Step 1: ingest one or more IGbulkDL JSON files.
# Usage: make ingest FILE=data/food.json
#        make ingest FILE="data/food.json data/desserts.json"
ingest:
	uv run python scripts/ingest_igbulkdl.py $(FILE)

# Step 2: submit AI batch (only recipes without instructions).
submit:
	uv run python scripts/extract_recipes.py submit

# Step 2 (force): re-submit everything — use after a prompt change.
submit-force:
	uv run python scripts/extract_recipes.py submit --force

# Step 3: check batch progress.
status:
	uv run python scripts/extract_recipes.py status

# Step 4: download and apply completed batch results.
apply:
	uv run python scripts/extract_recipes.py apply

# ── Dev ───────────────────────────────────────────────────────────────────────

serve-api:
	uv run uvicorn foodiegram.api:app --reload --port 8000

lint:
	uv run ruff check --fix src/ scripts/ && uv run ruff format src/ scripts/ && uv run mypy --strict src/

test:
	uv run pytest tests/
