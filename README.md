# Dispensa 🫙

A personal recipe library and Mediterranean-diet weekly meal planner.
~800 recipes extracted from saved Instagram posts (mostly Italian) plus, eventually,
manually added recipes. The signature feature: a **live, colour-coded weekly balance
panel** tracking 7 protein categories against Mediterranean targets — adding or
removing a recipe from the week moves the bars in real time and suggests gap-fillers.

ADHD-friendly, warm, editorial, accessible. Simple, readable, robust over clever.

> Repo name is `cookstagram` (historical); package rename to `dispensa` is deferred to
> Phase 5. See [docs/PLAN.md](docs/PLAN.md) for the full roadmap.

---

## Pipeline overview

Instagram extraction is **one ingestion source**, not the product. The pipeline runs
locally (~monthly) and pushes structured recipes into the database.

```
Instagram app (browse & save — keeps the account warm)
  ↓ IGbulkCollector (browser ext) → export post list
  ↓ IGbulkDL --dry-run → food.json (captions + CDN URLs)
  ↓ scripts/ingest_igbulkdl.py food.json   → recipe stubs + thumbnails → Cloudinary
  ↓ scripts/extract_recipes.py submit       → OpenAI Batch API (≈50% cheaper)
  ↓ scripts/extract_recipes.py status / apply → structured recipes
  ↓ (Phase 2+) scripts/promote.py → canonical recipe rows in DB
  ↓ (Phase 2+) scripts/export.py  → data/ backup in private repo

Web app: browse · search · plan weeks · (Phase 6) edit · add manual recipes
```

---

## Quick start (dev)

```bash
cp .env.example .env   # fill in OPENAI_API_KEY + CLOUDINARY_*
uv sync
make serve-api         # → http://localhost:8000
```

---

## Project layout

```
src/foodiegram/
  domain/        Pure models, enums, errors — no I/O, no SDKs
  storage/       JSON-backed RecipeRepository (SQLite in Phase 2)
  ai/            OpenAI Batch submit/status/apply; prompts/
  instagram/     instagrapi adapter, cache, auth
  images/        Cloudinary adapter (placeholder)
  app/           Use-case layer (placeholder)
  api.py         FastAPI: GET/PATCH /recipes + /scale
  api_models.py  API response models (RecipeSummary, RecipeDetail)
  settings.py    pydantic-settings (reads .env)
public/          SPA frontend (single index.html — split in Phase 4)
scripts/         Thin CLI wrappers over foodiegram.ai / foodiegram.instagram
tests/
docs/PLAN.md     Full roadmap, architecture decisions, all specs
```

---

## Runbook

> **Full runbook lives in [docs/PLAN.md §13](docs/PLAN.md).** It covers:
> syncing new saved posts, changing the extraction prompt, promoting to DB,
> exporting a backup, and running against Neon Postgres in prod.

Short form — ingesting new posts locally:

```bash
# 1. Export post list with IGbulkCollector (browser) → run IGbulkDL → food.json
make ingest FILE=data/food.json    # create recipe stubs

# 2. Extract with OpenAI Batch API
make submit                        # submit (or submit-force after a prompt change)
make status                        # check progress
make apply                         # write structured fields into recipes

# 3. Browse
make serve-api
```

---

## Makefile targets

| Target | What it does |
|---|---|
| `make check` | Full gate: ruff + mypy + pytest + lint-imports |
| `make serve-api` | Start FastAPI dev server on :8000 |
| `make ingest FILE=…` | Ingest an IGbulkDL JSON file |
| `make submit` | Submit OpenAI batch job |
| `make submit-force` | Re-submit all eligible recipes |
| `make status` | Check batch progress |
| `make apply` | Apply completed batch results |

---

## Environment

Copy `.env.example` and fill in the required variables. See the file for
descriptions of each group (OpenAI, Cloudinary, Database, Auth, Instagram).
