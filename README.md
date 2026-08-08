# Dispensa 🫙

A personal recipe library and Mediterranean-diet weekly meal planner.
~1,150 recipes extracted from saved Instagram posts (mostly Italian) plus, eventually,
manually added recipes. The signature feature: a **live, colour-coded weekly balance
panel** tracking 7 protein categories against Mediterranean targets — adding or
removing a recipe from the week moves the bars in real time and suggests gap-fillers.

ADHD-friendly, warm, editorial, accessible. Simple, readable, robust over clever.

> Repo name is `cookstagram` (historical); package rename to `dispensa` is deferred to
> Phase 5. See [docs/PLAN.md](docs/PLAN.md) for the full roadmap.

---

## Pipeline overview

Instagram extraction is **one ingestion source**, not the product. The pipeline runs
locally (~monthly) and pushes structured recipes into the database. The **database is
the source of truth**; the JSON files under `data/recipes/` are an import/export backup
kept in a separate private repo.

Extraction is **append-only**: `apply` records each LLM result as an immutable
`extractions` row and never mutates recipes. A separate `promote` step merges the latest
extraction into each recipe and **always preserves fields the user has edited**.

```
Instagram app (browse & save — keeps the account warm)
  ↓ IGbulkCollector (browser ext) → export post list
  ↓ IGbulkDL --dry-run → food.json (captions + CDN URLs)
  ↓ make ingest      → recipe stubs + thumbnails
  ↓ make submit      → OpenAI Batch API (≈50% cheaper)
  ↓ make status / apply → extractions rows (immutable history)
  ↓ make promote     → dry-run diff; make promote-apply → merge into recipes
  ↓ make export      → data/recipes/ backup, committed to the private data repo

Web app: browse · search · plan weeks · (Phase 6) edit · add manual recipes
```

---

## Quick start (dev)

```bash
cp .env.example .env   # serving needs no secrets; fill the pipeline block only to ingest
uv sync
make import            # load data/recipes/ into data/dispensa.db (first run only)
make serve-api         # → http://localhost:8000
```

The database defaults to `sqlite:///data/dispensa.db` (auto-created). Point at another
database — e.g. Neon Postgres in prod — by setting `DATABASE_URL`. Serving the app needs
only `DATABASE_URL` (+ `BASIC_AUTH_*` in prod); the OpenAI/Cloudinary/Instagram secrets
are used solely by the local ingestion pipeline.

---

## Project layout

```
src/foodiegram/
  domain/        Pure models, enums, errors, promote()/diff — no I/O, no SDKs
  storage/       DB-backed repositories (SQLModel); recipes_json.py = import/export
                 db.py · _tables.py · recipes_db.py · extractions_db.py · user_state_db.py
  ai/            OpenAI Batch build/submit/status/apply; prompts/; pydantic-ai repair
  instagram/     instagrapi adapter, cache, auth
  images/        Cloudinary adapter
  app/           Use-cases: import_json, export, promotion, diff_batch, review_categories
  api.py         FastAPI: GET/PATCH /recipes + /scale (serves from the DB)
  api_models.py  API response models (RecipeSummary, RecipeDetail)
  settings.py    pydantic-settings (reads .env); DATABASE_URL, OpenAI, Cloudinary
frontend/        SPA (no-build ES modules): css/ tokens+base+components, js/ views+components
scripts/         Thin CLI wrappers over foodiegram.app / foodiegram.ai
tests/
docs/PLAN.md     Full roadmap, architecture decisions, all specs
```

Dependencies point inward only (`api / scripts → app → storage | ai → domain`),
enforced by import-linter. The ORM (SQLModel/SQLAlchemy) never leaks outside `storage/`.

---

## Runbook

**Syncing new saved posts (~monthly, local):**

```bash
# 1. Browse/save on the phone as normal (keeps the account warm).
# 2. Run IGbulkCollector in the browser → export the post list.
# 3. IGbulkDL --dry-run → food.json (captions + CDN URLs; no media downloads).
make ingest FILE=data/food.json    # thumbnails upload NOW — CDN URLs expire
make submit                        # only recipes missing an extraction at v2
make status                        # wait for completed
make apply                         # download → extractions rows (history only)
make promote                       # dry-run: see what would change per recipe
make promote-apply                 # merge into recipes (user edits preserved)
make export                        # DB → data/recipes/; commit in the private data repo
```

**Changing the prompt or model:**

```bash
# Bump PROMPT_VERSION in src/foodiegram/ai/batch.py first (e.g. 2 → 3).
make submit-all                    # re-submit every captioned recipe
make apply
make diff FROM=2 TO=3              # aggregate: "what actually changed?"
make promote VERSION=3            # dry-run review
make promote-apply VERSION=3      # merge; user edits are never at risk
make export
```

**Against prod:** prefix any command with `DATABASE_URL=<neon-pooled-url>`, e.g.
`DATABASE_URL=… make promote-apply VERSION=3`.

**Disaster recovery / fresh clone:** `make import` loads `data/recipes/` back into the
DB; `make backfill` reconstructs `extractions` history from kept `batch_output.jsonl`.

**Instagram account note:** instagrapi login is currently flagged; nothing here depends
on it. Never run Instagram-facing code on the server.

---

## Deploy (FastAPI Cloud + Neon)

One `fastapi deploy` ships the API, the SPA, and the OAuth-protected MCP endpoint
together (D1). The served app is the composition root `foodiegram.asgi:app`
(declared under `[tool.fastapi]` in `pyproject.toml`), which mounts the
Basic-authed API at `/` and the MCP transport at `/mcp` behind OAuth 2.1. The
deploy artifact is **code only** — data reaches prod via a local `import_json`
against Neon (D2), and the filesystem is ephemeral (nothing mutable on disk in
prod).

The MCP endpoint is served at the exact path `https://<host>/mcp` (no trailing
slash — give clients that URL verbatim to avoid a redirect that would drop the
`Authorization` header). It runs stateless with single-shot JSON responses, so it
survives autoscaling. Auth is bearer-JWT: an unauthenticated request gets a `401`
with `WWW-Authenticate: Bearer resource_metadata="…"`, and the protected-resource
metadata is published at `https://<host>/.well-known/oauth-protected-resource/mcp`
(naming the IdP). Tokens must carry the `/mcp` URL as their audience (RFC 8707).

**Prerequisites**
- The app serves fine with only `DATABASE_URL` set; ingestion secrets are optional.
- FastAPI Cloud supports Python 3.14 (matches `requires-python`); pin `==3.14.*` only
  if a dependency later forces it.
- Tables + default targets are created automatically on first boot (`init_db`), so a
  fresh Neon database is fine — but load the recipe data before/right after first deploy.

**Steps**

```bash
# 1. Provision a Neon Postgres database; copy its POOLED connection string.
# 2. Load your data into Neon from your laptop (data never rides in the artifact):
DATABASE_URL='<neon-pooled-url>' make import

# 3. Deploy the code (from the repo root):
uvx fastapi deploy        # or: fastapi deploy

# 4. In the FastAPI Cloud dashboard, set env vars:
#      DATABASE_URL          = <neon-pooled-url>
#      BASIC_AUTH_USERNAME   = <you>
#      BASIC_AUTH_PASSWORD   = <strong-password>
#      MCP_OAUTH_ISSUER      = <idp-issuer-url>            # gates /mcp; boot fails if any unset
#      MCP_OAUTH_JWKS_URI    = <idp-jwks-uri>
#      MCP_OAUTH_RESOURCE_URL= https://<host>/mcp         # token audience (RFC 8707)
#      CORS_ALLOW_ORIGINS    = (leave empty — the SPA is same-origin)
```

**Smoke test after deploy:** open the URL (expect a Basic-auth prompt), load a recipe,
then edit something and redeploy — the edit must survive (proves the DB, not the
ephemeral disk, is the source of truth).

> Auth is enforced over **everything** (static + API) whenever `BASIC_AUTH_USERNAME` is
> set; leave it empty only for local dev.

---

## Makefile targets

| Target | What it does |
|---|---|
| `make check` | Full gate: ruff + mypy + pytest + lint-imports |
| `make serve-api` | Start FastAPI dev server on :8000 |
| `make import` | Load `data/recipes/` JSON into the DB |
| `make export` | Export the DB to `data/recipes/` (sorted-key JSON) |
| `make ingest FILE=…` | Ingest IGbulkDL JSON file(s) into the DB |
| `make submit` / `make submit-all` | Submit an OpenAI batch (only-missing / everything) |
| `make status` | Check batch progress |
| `make apply` | Download results into the `extractions` table |
| `make promote` / `make promote-apply` | Merge latest extractions into recipes (dry-run / write) |
| `make diff FROM=1 TO=2` | Aggregate diff between two prompt versions |
| `make backfill` | Rebuild extraction history from `batch_output.jsonl` |

Promote/diff default to `VERSION=2`; override per invocation (`make promote VERSION=3`).

---

## Environment

Copy `.env.example` and fill in the required variables. See the file for
descriptions of each group (OpenAI, Cloudinary, Database, Auth, Instagram).
