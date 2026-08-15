# scripts/ audit — phase 1 (read-only)

Classification of every file in `scripts/` (22 files) as of this audit, plus a
validated plan for the consolidated `sync` typer command group. **No files were
changed, moved, or deleted.** This is a proposal for review before phase 2.

Reference sources checked: `pyproject.toml` `[project.scripts]` (only
`foodiegram-api` → `api:main` and `foodiegram` → `cli:main`; **no script under
`scripts/` is a packaged entry point**), `Makefile`, `docs/PLAN.md`, `README.md`,
`tests/`, and a repo-wide grep of each module name. There is **no CI** (`.github/`
absent), so CI references are N/A.

Two facts that drive several classifications:

- `Recipe.from_extracted` already parses `base_servings` from the `servings`
  string (`src/foodiegram/domain/models.py:214-218`), so the extract→promote path
  populates it automatically now.
- Nothing in the ingest or extract path sets `author_username`; only
  `backfill_authors.py` ever did, and it reads the local instagrapi cache, which is
  frozen while the instagrapi login is flagged (`docs/PLAN.md:409-411`).

---

## Per-script table

| Script | Bucket | Reuses / imports | Referenced by | Reason |
|---|---|---|---|---|
| `ingest_igbulkdl.py` | CORE | `storage.recipes_db`, `domain.models`; DB only | Makefile `ingest`; PLAN §4/§12 | Stage-B reconcile of IGbulkDL `food.json` → recipe stubs; the documented ingest step. |
| `extract_recipes.py` | CORE | `app.extraction`, `ai.batch`; OpenAI + DB | Makefile `submit`/`status`/`apply`; PLAN §12/§13 | Thin wrapper over the OpenAI Batch extract use-case; the extract stage. |
| `promote.py` | CORE | `app.promotion`; DB only | Makefile `promote`/`promote-apply`; PLAN §4/§12 | The only extraction→recipe merge path; respects user edits. |
| `backfill_embeddings.py` | CORE | `ai.embeddings`, `storage`; OpenAI + DB | none (grep: self only) | Reusable, idempotent; the **only** code that writes `recipe_embeddings` → the embed stage of RAG. |
| `upload_thumbnails.py` | CORE | inline `cloudinary`, `storage.recipes_db`; Cloudinary + DB | none | Reusable image step: upload missing thumbnails to Cloudinary, store durable URL. Overlaps `fix_cdn_thumbnails.py`. |
| `fix_cdn_thumbnails.py` | CORE | inline `cloudinary`, `storage.recipes_db`; Cloudinary + DB | none | Reusable image-repair step: re-upload expired CDN thumbnails. Overlaps `upload_thumbnails.py` (different, subtly inconsistent filters). |
| `export.py` | CORE | `app.export`; DB only | Makefile `export`; PLAN §12/§13; README | Ongoing DB→JSON backup after every batch/edit session. |
| `import_json.py` | CORE | `app.import_json`; DB only | Makefile `import`; PLAN §12; README | Inverse of export; initial prod load + disaster recovery. |
| `diff_batch.py` | DEV | `app.diff_batch`; DB only | Makefile `diff`; PLAN §12/§13 | Diagnostic: "what changed between prompt versions?" Not part of `sync`; keep as standalone tool. |
| `review_categories.py` | DEV | `ai.repair`, `app.review_categories`; OpenAI + DB | PLAN §4/§12; `tests/test_review_categories.py` | Interactive, on-demand pydantic-ai category QA. Reusable; has tests. |
| `probe_get_recipe.py` | DEV | `mcp_server.server.get_recipe`; DB only | none | One-recipe MCP probe for spot-checking output. |
| `probe_semantic_search.py` | DEV | `app.search_recipes`; OpenAI + DB | none | Ad-hoc semantic-search probe (uses the real `find_similar` path). |
| `eval_search.py` | DEV | `ai.embeddings`; OpenAI + DB | none | Self-described "throwaway" search-quality check; embeds inline (does **not** use stored embeddings). Overlaps `probe_semantic_search.py` — candidates to merge. |
| `fetch_missing_posts.py` | DEV | `instagram` (extractor/cache); Instagram only | PLAN §13 | Convenience: fetch/refresh cached posts to renew CDN URLs. PLAN explicitly keeps it as a convenience if instagrapi recovers. |
| `instagram_login.py` | DEV | `instagram.login_client`; Instagram only | none | Prerequisite session creator for any instagrapi work (snapshot / fetch). Small, load-bearing when Instagram is used. |
| `backfill_extractions.py` | DEV | `ai.batch`, `storage.extractions_db`; DB only | Makefile `backfill`; PLAN §2.5 | Reconstructs append-only extraction history from kept `batch_output.jsonl`; disaster-recovery tool. KEEP (entry-referenced). |
| `import_existing.py` | DEAD | `storage.recipes_json` (legacy JSON store); disk only | none (docstring says `make import`, but that target runs `import_json.py`) | Spent one-off: first import of legacy cookstagram `index.json`/`extracted_recipes.json` into the JSON store. Superseded by the DB + `import_json.py`. |
| `migrate_drop_user_state_fields.py` | DEAD | `domain.models`; disk (legacy JSON) only | none | Spent migration: strips `user_notes`/`is_favorite` from legacy JSON files. Those fields are gone from `Recipe`; source of truth is now the DB. |
| `backfill_base_servings.py` | DEAD | `storage.recipes_db`; DB only | none | Spent backfill: `from_extracted` now parses `base_servings` (`models.py:214-218`), so the pipeline fills it going forward. |
| `backfill_authors.py` | DEAD | `instagrapi.types.Media`, `storage.recipes_db`; DB + local cache | none | Spent one-off "before copying the DB to prod" backfill; reads the now-frozen instagrapi cache. **Caveat:** it is the only tool that sets `author_username` — see gap G5 before deleting. |
| `snapshot_instagram.py` | NEEDS-ESTER-DECISION | `instagram.snapshot`, `instagram.InstagramExtractor`; Instagram + disk | `tests/test_snapshot_instagram.py` (both untracked/new) | Brand-new instagrapi Stage-A alternative that emits a `food.json`-shaped file — a drop-in replacement for the IGbulkCollector→IGbulkDL browser export, feeding the same `ingest_igbulkdl.py`. Redundant with the *browser* path, not with ingest. Login is flagged. Keep the instagrapi alternative or standardize on the browser path? |
| `copy_db.py` | NEEDS-ESTER-DECISION | `storage.maintenance`; SQLite + Postgres | none | SQLite→Postgres copy for the prod cutover / recovery. Is the cutover done (delete) or do you want it as a standing recovery tool alongside `cli db dump`/`restore`? |

---

## SAFE TO DELETE (DEAD)

Spent one-offs whose effect is already applied and which nothing references:

- `import_existing.py` — legacy cookstagram → JSON-store import, superseded by DB + `import_json.py`.
- `migrate_drop_user_state_fields.py` — legacy-JSON field-drop migration; fields removed from the model.
- `backfill_base_servings.py` — superseded by `from_extracted` (`models.py:214-218`).
- `backfill_authors.py` — spent pre-prod-copy backfill from the frozen cache. **Confirm gap G5 first** (it is the sole `author_username` writer).

## KEEP (CORE + DEV)

CORE — ongoing ingestion / RAG workflow (consolidate into `sync`, see below):
`ingest_igbulkdl.py`, `extract_recipes.py`, `promote.py`, `backfill_embeddings.py`,
`upload_thumbnails.py`, `fix_cdn_thumbnails.py`, `export.py`, `import_json.py`.

DEV — probes / eval / QA / prerequisites worth keeping:
`diff_batch.py`, `review_categories.py`, `probe_get_recipe.py`,
`probe_semantic_search.py`, `eval_search.py`, `fetch_missing_posts.py`,
`instagram_login.py`, `backfill_extractions.py`.

- Overlap to merge (phase 2): `eval_search.py` and `probe_semantic_search.py` both
  rank queries against recipes; `eval_search` embeds inline and ignores stored
  embeddings, so it does not exercise the real path. Fold into one probe that uses
  `find_similar`.

## NEEDS-ESTER-DECISION

- `snapshot_instagram.py` (+ new `src/foodiegram/instagram/snapshot.py` and
  `tests/test_snapshot_instagram.py`) — keep the instagrapi Stage-A alternative to
  the browser export, or standardize on IGbulkCollector→IGbulkDL and drop it? It is
  new, tested, uncommitted work; the redundancy is with the browser path, and the
  instagrapi login is currently flagged.
  *To decide:* do you want a code-only Stage-A path that does not depend on the
  browser extension, given the login risk?
- `copy_db.py` — is the SQLite→Postgres cutover complete (delete), or should it stay
  as a recovery utility next to `cli db dump`/`restore`?
  *To decide:* is `data/dispensa.db` still a source you copy from?

---

## Validated `sync` pipeline plan (typer command group)

Target: a `sync` group with `dedupe-links`, `ingest`, `extract`, `promote`,
`embed --changed`, and `all` (orchestrates the four). Reuse mapping and gaps below;
each stage names the module that already holds the logic.

| `sync` stage | Reuse (existing logic) | Notes / what the design would drop |
|---|---|---|
| `dedupe-links` | **No existing script.** Closest: `instagram.snapshot.known_shortcodes()` and `RecipeRepository.exists`/`.get` (used in `ingest_igbulkdl._process_item`). | New logic. Nothing today dedupes the IGbulkCollector `.txt` link export against the DB before download. See gap G1. |
| `ingest` (new? / image missing-or-broken → Cloudinary / caption changed?) | `ingest_igbulkdl.py` (`_parse_items`, `_process_item`) for new?/known; `upload_thumbnails.py` + `fix_cdn_thumbnails.py` for the Cloudinary image logic. | Current `ingest_igbulkdl` **only backfills caption when null** — it never updates a *changed* caption (gap G2). It does **not** upload thumbnails at ingest (D14 deferred) — image upload is still two separate scripts (gap G3). It **drops `author`**, which `food.json`/snapshot already carries (gap G5). |
| `extract` (OpenAI batch, v3 prompt) | `extract_recipes.py` → `app.extraction.submit_batch`/`apply_batch` → `ai.batch` (`PROMPT_VERSION`, prompts in `ai/prompts/`). | `PROMPT_VERSION` is `"2"` today and the prompt file is `extract_recipe_details.txt`; a **v3 prompt + version bump** does not exist yet (gap G4). `--only-missing` semantics already exist. |
| `promote` | `promote.py` → `app.promotion.promote_version` (dry-run/apply, skips `edited_fields`). | Direct reuse; no gap. |
| `embed --changed` | `backfill_embeddings.py` (`backfill_embeddings`, `_embedded_codes`). | Current logic skips codes that **already have an embedding row** (presence-based) or re-embeds all with `--force`. There is **no staleness/`--changed` detection** — no tracking of whether the recipe changed since it was embedded (gap G6). `--changed` semantics must be built. |
| `all` | Orchestrate the four above in order. | Decide whether `all` also runs `dedupe-links` and the image step, and whether it stops on the first stage error. |

### Gaps to resolve in phase 2

- **G1 — `dedupe-links` has no home.** No current script parses/dedupes the
  IGbulkCollector `.txt` export against the DB. Needs new logic (reuse
  `RecipeRepository.exists` / `known_shortcodes`).
- **G2 — caption-change detection.** `ingest_igbulkdl` backfills a caption only
  when the stored one is empty; it will not pick up an edited caption. The `sync`
  "caption changed?" branch is new behaviour.
- **G3 — image logic is inline in two scripts.** `upload_thumbnails.py` and
  `fix_cdn_thumbnails.py` both call the Cloudinary SDK directly with **different,
  inconsistent filters** (`upload_thumbnails` skips captioned recipes and only fills
  a missing `cloudinary_url`; `fix_cdn` targets CDN-prefixed URLs and rewrites
  `thumbnail_url`). The `images/` package is an **empty placeholder**
  (`images/__init__.py` is empty). Consolidate a single Cloudinary adapter in
  `images/` and reconcile the two filters before folding into `ingest`.
- **G4 — v3 prompt/version.** `ai/batch.PROMPT_VERSION` is `"2"`; a v3 prompt and
  version bump must be authored; `Makefile VERSION ?= 2` also assumes v2.
- **G5 — `author_username` population.** No ingest/extract path sets it. If
  `backfill_authors.py` is deleted, nothing writes authors. `snapshot.py` already
  captures `author` into `food.json`, but `ingest_igbulkdl._parse_items` discards
  it (it maps `pk` from the `username` field and ignores `author`). Decide where
  authors come from going forward before deleting the backfill.
- **G6 — `embed --changed` needs change tracking.** Only presence-based skip exists
  today; there is no record of the document/hash an embedding was built from.
