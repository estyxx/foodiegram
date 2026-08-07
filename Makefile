.PHONY: ingest submit submit-all status apply promote promote-apply diff \
        export import backfill serve-api lint test typecheck lint-imports check

# Prompt version to promote/diff. Bump PROMPT_VERSION in ai/batch.py in step.
VERSION ?= 2

# ── Pipeline ──────────────────────────────────────────────────────────────────

# Step 1: ingest one or more IGbulkDL JSON files into the DB.
# Usage: make ingest FILE=data/food.json
#        make ingest FILE="data/food.json data/desserts.json"
ingest:
	uv run python scripts/ingest_igbulkdl.py $(FILE)

# Step 2: submit an AI batch (only recipes missing an extraction at the current
# prompt version). Use submit-all after a prompt/model change.
submit:
	uv run python scripts/extract_recipes.py submit

submit-all:
	uv run python scripts/extract_recipes.py submit --all

# Step 3: check batch progress.
status:
	uv run python scripts/extract_recipes.py status

# Step 4: download completed results into the extractions table (never touches
# recipes). Run promote afterwards to merge them in.
apply:
	uv run python scripts/extract_recipes.py apply

# Step 5: preview / apply promotions. Dry-run by default; promote-apply writes.
promote:
	uv run python scripts/promote.py --version $(VERSION)

promote-apply:
	uv run python scripts/promote.py --version $(VERSION) --apply

# What changed between two prompt versions? Usage: make diff FROM=1 TO=2
diff:
	uv run python scripts/diff_batch.py --from-version $(FROM) --to-version $(TO) --summary

# Step 6: export the DB to data/recipes/ (commit in the private data repo).
export:
	uv run python scripts/export.py

# Load data/recipes/ into the DB (initial load / disaster recovery).
import:
	uv run python scripts/import_json.py

# Reconstruct extraction history from kept batch_output.jsonl files.
backfill:
	uv run python scripts/backfill_extractions.py

# ── Dev ───────────────────────────────────────────────────────────────────────

serve-api:
	uv run uvicorn foodiegram.api:app --reload --port 8000

lint:
	uv run ruff check --fix src/ scripts/ && uv run ruff format src/ scripts/ && uv run mypy --strict src/

test:
	uv run pytest tests/

# Type-check the frontend (checkJs). The single JS devDependency is typescript.
typecheck:
	npx tsc --noEmit -p frontend/jsconfig.json

# Enforce the layering contracts declared under [tool.importlinter] in pyproject.
lint-imports:
	uv run lint-imports

# Full gate: ruff + mypy + pytest + import-linter + frontend types.
check:
	uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest && $(MAKE) lint-imports && $(MAKE) typecheck
