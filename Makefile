.PHONY: ingest submit submit-all status apply promote promote-apply diff \
        export import backfill db-init serve-api serve-all lint test typecheck \
        lint-imports js-test check

# Prompt version to promote/diff. Bump PROMPT_VERSION in ai/batch.py in step.
VERSION ?= 3

# ── Pipeline ──────────────────────────────────────────────────────────────────

# Step 1: ingest an IGbulkDL JSON file into the DB.
# Usage: make ingest FILE=data/food.json
ingest:
	uv run dispensa sync ingest $(FILE)

# Step 2: submit an AI batch (only recipes missing an extraction at the current
# prompt version). Use submit-all after a prompt/model change.
submit:
	uv run dispensa sync extract

submit-all:
	uv run dispensa sync extract --all

# Step 3: check batch progress.
status:
	uv run dispensa sync status

# Step 4: download completed results into the extractions table (never touches
# recipes). Run promote afterwards to merge them in.
apply:
	uv run dispensa sync apply

# Step 5: preview / apply promotions. Dry-run by default; promote-apply writes.
promote:
	uv run dispensa sync promote --version $(VERSION)

promote-apply:
	uv run dispensa sync promote --version $(VERSION) --apply

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

# Create local Postgres databases (working + test) and schema.
db-init:
	uv run dispensa db create-database
	uv run dispensa db create-database --test
	uv run dispensa db create-tables

serve-api:
	uv run uvicorn dispensa.api:app --reload --port 8000

# Serve the composed app (API + Bearer-gated /mcp) via the [tool.fastapi]
# entrypoint, exactly as FastAPI Cloud does. Requires MCP_AUTH_TOKEN in the env.
serve-all:
	uv run fastapi dev

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

# Unit tests for the pure frontend modules (Node's built-in runner, no deps).
js-test:
	node --test frontend/tests/*.test.js

# Full gate: ruff + mypy + pytest + import-linter + frontend types.
check:
	uv run ruff check --fix . && uv run ruff format . && uv run mypy . && uv run pytest && $(MAKE) lint-imports && $(MAKE) typecheck && $(MAKE) js-test
