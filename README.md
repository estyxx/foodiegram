# Foodiegram

Extracts saved Instagram posts from a collection, uses an LLM to turn captions
into structured recipes, and serves a browsable site with search and filtering.

---

## Full pipeline: Instagram saved collection → extracted recipes

### Step 0a — Collect post links (browser, one-time per collection)

Install **[IGbulkCollector](https://github.com/doncezart/IGbulkCollector)** as a
Tampermonkey userscript.

1. Go to your Instagram saved collection
   (`instagram.com/<you>/saved/all-posts/` or a specific named collection)
2. The IGbulkCollector panel appears — click **▶ Start** and let it auto-scroll
3. Click **⤓ Export .txt** — saves a file with one URL per line:
   ```
   https://www.instagram.com/p/DZXr3-aMxqg/
   https://www.instagram.com/p/DZIT2TGtRus/
   ```
4. Save it somewhere you can point IGbulkDL at (e.g. `data/collection.txt`)

---

### Step 0b — Download captions + metadata (IGbulkDL)

Install **[IGbulkDL](https://github.com/doncezart/IGbulkDL)**.

```bash
# GUI (easiest):
python ig_gui.py
# fill in: URL file = data/collection.txt, collection name = food, cookies file = cookies.txt
# click Start

# or CLI:
python ig_download.py data/collection.txt food --cookies cookies.txt
```

This produces `food.json` — one entry per post with `shortcode`, `caption`,
`title`, `status`, etc. Move it to `data/food.json` (or keep the name — you
pass it explicitly in the next step).

> **Cookies:** export your Instagram browser cookies via a cookie-export extension
> (e.g. "Get cookies.txt LOCALLY") and save as `cookies.txt`.

---

### Step 1 — Ingest into the recipe repository

Creates `data/recipes/{shortcode}.json` stubs with caption + thumbnail.
Already-present recipes are only updated if `caption` or `thumbnail_url` is
currently missing — AI-extracted fields are never touched.

```bash
uv run python scripts/ingest_igbulkdl.py data/food.json
```

Pass multiple files if you have more than one collection:
```bash
uv run python scripts/ingest_igbulkdl.py data/food.json data/desserts.json
```

---

### Step 2 — Submit to OpenAI Batch API

Sends all stubs that have a caption but no instructions to `gpt-4.1-mini`.
~50% cheaper than real-time calls. Saves the batch ID to `data/last_batch_id.txt`.

```bash
uv run python scripts/extract_recipes.py submit

# Re-run everything after a prompt change:
uv run python scripts/extract_recipes.py submit --force
```

---

### Step 3 — Check batch status

```bash
uv run python scripts/extract_recipes.py status
```

Usually completes within minutes; guaranteed within 24 hours.

---

### Step 4 — Apply results

Downloads the completed batch output and writes structured fields (title,
ingredients, instructions, tags, confidence…) into each recipe JSON.
Preserves `is_favorite`, `user_notes`, `cloudinary_url`, and anything
`edited_by_user`.

```bash
uv run python scripts/extract_recipes.py apply
```

---

### Done — browse the recipes

```bash
make serve-api
# → http://localhost:8000
```

---

## Makefile quick reference

```bash
make ingest FILE=data/food.json   # Step 1 — ingest one IGbulkDL file
make submit                       # Step 2 — submit AI batch
make submit-force                 # Step 2 — force re-submit everything
make status                       # Step 3 — check batch status
make apply                        # Step 4 — apply batch results
make serve-api                    # Start the API + frontend
make lint                         # ruff + mypy
make test                         # pytest
```

---

## Project layout

```
public/            SPA frontend (single index.html)
scripts/           CLI scripts for the pipeline
src/foodiegram/
  domain/          Pure models, enums, errors — no I/O
  prompts/         LLM prompt templates (.txt)
  api.py           FastAPI: /recipes CRUD + /scale
  repository.py    JSON-backed recipe store
  settings.py      pydantic-settings (reads .env)
data/
  recipes/         One {code}.json per recipe (git-ignored)
```

## Environment (.env)

```
OPENAI_API_KEY=sk-...
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
CLOUDINARY_URL=cloudinary://...
# Instagram fields not required if using IGbulkDL
INSTAGRAM_USERNAME=
INSTAGRAM_PASSWORD=
INSTAGRAM_COLLECTION_ID=
INSTAGRAM_SESSION_FILE=data/session.json
```
