# Dispensa 🫙

A personal recipe library and Mediterranean-diet weekly meal planner.
~1,180 recipes extracted from saved Instagram posts (mostly Italian) plus, eventually,
manually added recipes. The signature feature: a **live, colour-coded weekly balance
panel** tracking 8 protein categories against Mediterranean targets — adding or
removing a recipe from the week moves the bars in real time and suggests gap-fillers.

ADHD-friendly, warm, editorial, accessible. Simple, readable, robust over clever.

> Repo name is `cookstagram` (historical); package rename to `dispensa` is deferred to
> Phase 5. See [docs/PLAN.md](docs/PLAN.md) for the full roadmap.

---

## Pipeline overview

Instagram extraction is **one ingestion source**, not the product. The pipeline runs
locally (~monthly) and pushes structured recipes into **local Postgres — the source of
truth**. Neon (prod) is downstream; it never runs extraction or embedding itself.

Extraction is **append-only and asynchronous**: `extract` submits an OpenAI Batch job
and returns immediately; `apply` — once the batch completes — records each LLM result
as an immutable `extractions` row and never touches `recipes`. A separate `promote`
step merges the latest extraction into each recipe and **always preserves fields the
user has edited**. Semantic search (RAG) needs its own step too: `embed` re-embeds only
recipes whose extracted content actually changed.

```
Instagram app (browse & save — keeps the account warm)
  ↓ IGbulkCollector (browser ext) → export post list
  ↓ IGbulkDL --dry-run                     → food.json (captions + CDN URLs)
  ↓ foodiegram sync ingest food.json       → recipe stubs + Cloudinary thumbnails
  ↓ foodiegram sync extract                → submits an OpenAI Batch (async)
  ↓ foodiegram sync status   (optional)    → poll batch completion
  ↓ foodiegram sync apply                  → extractions rows (immutable history)
  ↓ foodiegram sync promote --apply        → merge into recipes (user edits preserved)
  ↓ foodiegram sync embed --changed        → re-embed recipes whose document changed

Web app: browse · search (keyword + AI/semantic) · plan weeks · edit · add manual recipes
```

`foodiegram sync backfill-images` is a separate maintenance command: it scans every
recipe already in the DB (not just the recipes in one `food.json` batch) and re-uploads
a Cloudinary image for any that are missing one — useful for recipes ingested before
Cloudinary upload was wired in, or whose upload failed the first time.

---

## Quick start (dev)

```bash
cp .env.example .env
uv sync
uv run foodiegram db create-database         # working DB
uv run foodiegram db create-database --test  # test DB (pytest only ever uses this one)
uv run foodiegram db create-tables
uv run uvicorn foodiegram.api:app --reload --port 8000
```

`DATABASE_URL` defaults to local Postgres (`postgresql+psycopg2://dispensa:dispensa@
localhost:5432/dispensa`) — see `.env.example`. Serving the app needs only
`DATABASE_URL` (+ `BASIC_AUTH_*` in prod); the OpenAI/Cloudinary/Instagram secrets are
used solely by the local ingestion pipeline below.

---

## Project layout

```
src/foodiegram/
  domain/        Pure models, enums, errors + pure logic (planning, pantry, shopping,
                 promote()/diff, synonyms) — no I/O, no SDKs
  storage/       Postgres-backed repositories (SQLModel rows never leave this package):
                 db.py · _tables.py · recipes_db.py · extractions_db.py ·
                 plans_db.py · pantry_db.py · targets_db.py · user_state_db.py ·
                 maintenance.py (dump/restore/reset) · recipes_json.py (legacy JSON)
  ai/            OpenAI: batch.py (Batch API submit/status/apply), embeddings.py (RAG),
                 repair.py (pydantic-ai interactive re-extraction), prompts/*.txt
  images/        Cloudinary adapter: upload_thumbnail + is_valid_image_ref
  instagram/     instagrapi adapter, cache, auth (flagged/frozen — see below)
  app/           Use-cases, one concern per module: ingest, extraction, backfill_images,
                 promotion, embed, diff_batch, review_categories, plan_week, export,
                 import_json, search_recipes, sync_all
  routers/       FastAPI routers: recipes, plans, pantry, targets, meta
  api.py         create_app() factory: Basic auth, gzip, CORS, serves the SPA
  mcp_server.py  MCP server exposing recipes/planning to Claude (OAuth-gated /mcp)
  asgi.py        Composition root mounting api + mcp_server (what FastAPI Cloud serves)
  cli.py         Typer CLI: `foodiegram db …` (maintenance) and `foodiegram sync …`
                 (the ingestion pipeline) — the primary way to run everything below
  settings.py    pydantic-settings (reads .env); DATABASE_URL, OpenAI, Cloudinary, auth
frontend/        SPA (no-build ES modules): css/ tokens+base+components, js/ views+components
scripts/         Legacy thin argparse wrappers predating the typer CLI — export.py and
                 import_json.py are still the only way to run those two use-cases (see
                 "Promoting to prod" below); most others are superseded by `sync …`.
tests/
docs/PLAN.md     Full roadmap, architecture decisions, all specs
```

Dependencies point inward only (`cli → app → storage | ai | images | instagram →
domain`), enforced by import-linter (`uv run lint-imports`). The ORM never leaks
outside `storage/`.

---

## The sync pipeline

Everything below is `uv run foodiegram sync <command>`. Writes (`ingest`, `apply`,
`promote --apply`, `embed`, `backfill-images`) print the target database and refuse a
production-looking host (`neon.tech`/`neon.build`) unless you pass `--yes` — this
pipeline is meant to run against **local** Postgres.

| Command | What it does |
|---|---|
| `dedupe-links <links.txt>` | Drop duplicate and already-known shortcodes from an IGbulkCollector links file before feeding it to IGbulkDL. |
| `ingest <food.json> --yes` | Per shortcode: new? / caption changed? / image missing or broken? Creates recipe stubs and uploads Cloudinary thumbnails **immediately** — Instagram's CDN URLs expire. |
| `backfill-images [--dry-run] --yes` | Scans every recipe in the DB (not just one `food.json`) and re-uploads a durable image for any still missing one. Recovers from a per-recipe upload failure (e.g. a deleted Instagram post) and reports it rather than aborting the whole run. |
| `extract [--limit N] [--all] [--codes …] [--dry-run]` | Submits an OpenAI Batch job for recipes needing extraction at the current `PROMPT_VERSION`. **Async** — returns immediately; the batch completes later. |
| `status [--batch id]` | Polls an OpenAI batch and prints its completion counts. Optional — just a convenience while waiting. Defaults to the last submitted batch. |
| `apply [--batch id] --yes` | Once the batch is `completed`, downloads its output and appends `extractions` rows. **Never touches `recipes`.** Required before `promote` — skipping this leaves `promote` with nothing to promote (`considered=0`). |
| `promote [--version V] [--batch id] [--apply] --yes` | Merges the latest extraction at a prompt version into each recipe. Dry-run by default; `--apply` writes. Always preserves fields the user has edited. |
| `embed [--force] [--codes …] [--dry-run] --yes` | Re-embeds recipes whose `recipe_document()` changed since their last embed (or that have no embedding yet). `--force` re-embeds everything. |
| `all <food.json> [--dry-run] --yes` | Runs `ingest → extract → promote → embed --changed` in order, stopping on first error. **Does not** poll `status` or run `apply` — `extract` is async, so `all` can't wait out a batch; run `status`/`apply`/`promote` by hand once it completes. |

**A full sync, start to finish:**

```bash
# 1. Browse/save on the phone as normal (keeps the account warm).
# 2. IGbulkCollector (browser ext) → export post list.
# 3. IGbulkDL --dry-run → food.json (captions + CDN URLs; no media downloads).

uv run foodiegram sync ingest data/food.json --yes
uv run foodiegram sync extract --limit 300         # or omit --limit for everything eligible

# … wait for the OpenAI batch to complete …
uv run foodiegram sync status --batch <batch_id>   # optional, poll until "completed"
uv run foodiegram sync apply --batch <batch_id> --yes

uv run foodiegram sync promote --apply --yes
uv run foodiegram sync embed --changed --yes
```

Submitting produces one batch per call; if you have several outstanding, apply each
archived batch (`data/batch_inputs/*.jsonl`) before promoting:

```fish
for f in data/batch_inputs/*.jsonl
    set batch (basename $f .jsonl)
    uv run foodiegram sync apply --batch $batch --yes
end
uv run foodiegram sync promote --apply --yes
```

**Changing the prompt or model:**

```bash
# Bump PROMPT_VERSION in src/foodiegram/ai/batch.py first (e.g. 2 → 3).
uv run foodiegram sync extract --all --yes    # re-submit every captioned recipe
# … status / apply as above …
uv run foodiegram sync promote --version 3 --apply --yes   # user edits are never at risk
uv run foodiegram sync embed --changed --yes
```

**Instagram account note:** the instagrapi login is currently flagged/frozen; nothing
in `sync` depends on it — it only ever reads a `food.json` that already exists. Never
run Instagram-facing code on the server.

---

## Database maintenance

```bash
uv run foodiegram db ping                   # connect and report success
uv run foodiegram db create-database        # create $DATABASE_URL if missing
uv run foodiegram db create-tables          # create any missing tables
uv run foodiegram db dump [--output PATH]   # pg_dump -Fc → backups/dispensa-<ts>.dump
uv run foodiegram db restore <dump> --yes   # pg_restore --clean into the working DB
uv run foodiegram db reset --yes            # drop + recreate every table (local only)
```

`dump`/`restore` shell out to `pg_dump`/`pg_restore`, which must be the **same major
version as the Postgres server** (they refuse to talk to a newer server than
themselves). If your server is newer than the `pg_dump` on `PATH` — e.g. Postgres.app
running Postgres 18 while your system package manager only has 17 — run the command
through a matching version instead of installing over your `PATH`:

```bash
nix shell nixpkgs#postgresql_18 -c uv run foodiegram db dump
```

`restore`/`reset` refuse a production-looking host (`neon.tech`/`neon.build`) even with
`--yes` passed through the normal guard — they're wholesale, destructive, whole-DB
operations meant for the **local working database only**, never Neon. See "Promoting to
prod" below for how data actually reaches Neon.

---

## Promoting to prod (Neon)

Local Postgres is the source of truth; Neon is downstream. **Extraction never runs
against Neon** — everything above (`extract`/`apply`/`promote`/`embed`/
`backfill-images`) happens locally, and only the *result* moves to prod, so nothing
gets re-extracted or re-uploaded to Cloudinary just because it's landing in a new
database.

The mechanism today is a JSON export/import pair (not yet wired into the `sync`/`db`
typer CLI — reach them as standalone scripts):

```bash
uv run python scripts/export.py                              # DB → data/recipes/*.json
DATABASE_URL='<neon-pooled-url>' uv run python scripts/import_json.py
```

`export` writes one sorted-key JSON file per recipe (stable git diffs; commit the
output in the private data repo). `import_json` is the inverse: it upserts each
recipe — including its `cloudinary_url`, already durable and host-independent — plus
migrates any `is_favorite`/`user_notes` into `user_state`.

**Known gap:** this does **not** carry `recipe_embeddings` (the RAG vectors) or the
`extractions` history table — only the final promoted `recipes` rows. After importing
into Neon, semantic search needs its own pass there:

```bash
DATABASE_URL='<neon-pooled-url>' uv run foodiegram sync embed --changed --yes
```

That's an OpenAI embedding call per recipe (cheap — nothing like extraction cost) but
it is real recomputation, not a copy. A byte-identical embeddings copy is possible but
isn't built yet.

---

## Deploy (FastAPI Cloud + Neon)

One `fastapi deploy` ships the API, the SPA, and the OAuth-protected MCP endpoint
together (D1). The served app is the composition root `foodiegram.asgi:app`
(declared under `[tool.fastapi]` in `pyproject.toml`), which mounts the
Basic-authed API at `/` and the MCP transport at `/mcp` behind OAuth 2.1. The
deploy artifact is **code only** — data reaches prod via the export/import flow
above (D2), and the filesystem is ephemeral (nothing mutable on disk in prod).

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
  fresh Neon database is fine — but load the recipe data before/right after first deploy
  (see "Promoting to prod" above).

**Steps**

```bash
# 1. Provision a Neon Postgres database; copy its POOLED connection string.
# 2. Load your data into Neon from your laptop (data never rides in the artifact) —
#    see "Promoting to prod" above.

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

## Environment

Copy `.env.example` and fill in the required variables. See the file for
descriptions of each group (Runtime, OpenAI, Cloudinary, Instagram).

---

## Testing & the green gate

```bash
uv run ruff check --fix . && uv run ruff format . && uv run mypy src && uv run pytest -q && uv run lint-imports
```

Also available as the `/green` skill. Tests never touch the working database — only
`DATABASE_URL_TEST` (create it once with `uv run foodiegram db create-database --test`).
