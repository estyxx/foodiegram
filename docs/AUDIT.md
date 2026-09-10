# Dispensa — Reality Audit

Derived from the working tree at branch `main` (commit `26cc3fd`), not from the
docs. `docs/PLAN.md` and `docs/scripts-audit.md` are both behind the code; every
divergence is listed below with file references. No code was changed.

Ranking key: **P0** blocks a listed PLAN next step · **P1** data integrity ·
**P2** performance · **P3** cosmetic / doc drift.

---

## 0. Ranked findings (most severe first)

| # | Pri | Finding | Anchor |
|---|-----|---------|--------|
| F1 | P0 | **D12 client-side search cache does not exist.** Browse re-fetches the whole filtered corpus from the server on every keystroke / filter / favourite toggle; lexical search and filtering are server-side. PLAN 4.3 is unstarted despite 4.1 done and 4.2 substantially done. | [browse.js:145](../frontend/js/views/browse.js#L145), [client.js:193](../frontend/js/api/client.js#L193) |
| F2 | P0 | **`state/store.js` (the D7 pub-sub store) is dead code** — imported by nothing. Every view hand-rolls local closures + `renderAll()`. The frontend architecture PLAN §14 assumes is not in place, which is the substrate 4.3/4.4 were meant to build on. | [store.js:18](../frontend/js/state/store.js#L18) |
| F3 | P0 | **`#week` (Home) route does not exist** and was silently moved to Phase 5. `main.js` routes only `browse`/`plan`/`favourites`/`recipe`. PLAN 4.4 lists `#week` + `#plan`; only `#plan` is built. | [main.js:30](../frontend/js/main.js#L30), [plan.js:22](../frontend/js/views/plan.js#L22) |
| F4 | P0 | **Phase 6 write API is absent.** No `POST /api/recipes`, no `POST /api/recipes/extract-text`, no `DELETE /api/recipes/{code}`. `PATCH` accepts only `is_favorite` / `user_notes` / `base_servings`. `Recipe.archived` exists but no code path reads it. | [routers/recipes.py:270](../src/dispensa/routers/recipes.py#L270) |
| F5 | P1 | **"Caption changed → re-extract" is not wired.** `sync ingest` flags caption-changed codes, but `sync extract` (default `--only-missing`) skips any code already extracted at the current `PROMPT_VERSION`, which a caption-changed recipe always is. Re-extraction needs a manual `--all` / `--codes`. | [extraction.py:38](../src/dispensa/app/extraction.py#L38), [ingest.py:172](../src/dispensa/app/ingest.py#L172) |
| F6 | P1 | **`recipes.caption_hash` column is written but never read.** `_to_row` stores it; `_to_domain` drops it; `sync ingest` recomputes hashes from caption text on both sides. The mechanism CLAUDE.md documents ("`caption_hash` drives change-detection") is not the implemented one. | [recipes_db.py:35](../src/dispensa/storage/recipes_db.py#L35), [ingest.py:209](../src/dispensa/app/ingest.py#L209) |
| F7 | P1 | **Two edit-tracking mechanisms; `save()` keys off the deprecated one.** `RecipeRepository.save` preserves `edited_fields` only when the stored row has `edited_by_user=True`. `edited_by_user` is marked "retired". A row with `edited_fields` set but the bool `False` would have its edits overwritten by any non-`promote` `save()`. | [recipes_db.py:225](../src/dispensa/storage/recipes_db.py#L225), [models.py:171](../src/dispensa/domain/models.py#L171) |
| F8 | P1 | **`posts` staging table is defined but never read or written.** No `storage/` or `app/` code touches `PostRow`. `sync ingest` writes recipe stubs directly. PLAN §10 / lifecycle diagram assume a `posts` stage. | [_tables.py:106](../src/dispensa/storage/_tables.py#L106) |
| F9 | P2 | **Semantic search is pure-Python cosine with no vector cache.** `find_similar` re-`SELECT`s and JSON-parses every candidate embedding row on every query, then loops `cosine_similarity` in CPython. Fine at 1k (~0.1–0.2 s/query); ~0.5–1 s/query at 5k. No `_all_cache` equivalent for embeddings. | [recipes_db.py:364](../src/dispensa/storage/recipes_db.py#L364), [similarity.py:4](../src/dispensa/domain/similarity.py#L4) |
| F10 | P2 | **MCP `search_recipes` returns summary-only rows.** Slim view (no ingredients/instructions/categories/times). A model planning a week must call `get_recipe` per hit. By design, but flagged per audit scope. | [serializers.py:9](../src/dispensa/mcp_server/serializers.py#L9), [server.py:42](../src/dispensa/mcp_server/server.py#L42) |
| F11 | P2 | **Browse fires 2 requests per interaction and re-serialises the full corpus.** `getAllRecipes` + `getRecipeCounts` in parallel on every `apply()`, paged in 500-row chunks. Same fetch after every favourite toggle. | [browse.js:160](../frontend/js/views/browse.js#L160) |
| F12 | P3 | PLAN Phase 0, 1, and 4 checkboxes are all `[ ]` while the work is done or superseded (details §1). | [PLAN.md:548](PLAN.md#L548) |
| F13 | P3 | **`PROMPT_VERSION = "3"`**, PLAN says `"2"` throughout Part VII / §D6; Makefile `VERSION ?= 3`. | [batch.py:28](../src/dispensa/ai/batch.py#L28) |
| F14 | P3 | **Two parallel entrypoints.** `Makefile` targets call `scripts/*.py`; README + `cli.py` use `dispensa sync …`. `docs/scripts-audit.md` is stale (claims `PROMPT_VERSION` 2, `images/` an "empty placeholder" — both false). | [Makefile:13](../Makefile#L13) |
| F15 | P3 | `tests/test_architecture.py` (PLAN §3 / 0.3) was never created; import-linter replaced it (acknowledged in CLAUDE.md addendum, not in PLAN). `scripts/migrate_user_state.py` (PLAN §11) and `scripts/repair_recipe.py` (PLAN §12) were never created. | [pyproject.toml:120](../pyproject.toml#L120) |
| F16 | P3 | `frontend/schiena.html` — a self-contained Italian back-exercise page — is served at `/schiena.html` and is absent from PLAN. Unrelated to the product. | [schiena.html:13](../frontend/schiena.html#L13), [api.py:67](../src/dispensa/api.py#L67) |
| F17 | P3 | 4 spent one-off scripts still in `scripts/` (`import_existing.py`, `migrate_drop_user_state_fields.py`, `backfill_base_servings.py`, `backfill_authors.py`) per the repo's own `scripts-audit.md`. | [scripts-audit.md:53](scripts-audit.md#L53) |

**Not a next step but the likely reason for this audit:** no table carries a
household/user scope column, and four constraints would have to change for
multi-user (§4). Treated as informational — nothing in PLAN (incl. D16) tracks
multi-user.

---

## 1. PLAN.md checkboxes whose real status differs

| Item | Doc | Reality |
|---|---|---|
| 0.1 Recipe Detail missing fields | `[ ]` | External (Notion) — cannot verify from tree. |
| 0.2 Delete legacy files, add `.env.example` | `[ ]` | **Done.** No `recipe_extractor.py` / `login.html` / `recipe.js` / `.cursor/` in tree; `.env.example` tracked. |
| 0.3 DDD restructure + `tests/test_architecture.py` | `[ ]` | **Restructure done** ([src/dispensa/](../src/dispensa/) has domain/app/storage/ai/images/instagram/routers). `test_architecture.py` **not created** — replaced by `[tool.importlinter]` 3 contracts ([pyproject.toml:120](../pyproject.toml#L120)). |
| 0.4 README brief + CLAUDE.md JS/boundary rules | `[ ]` | **Done.** README rewritten ([README.md:1](../README.md#L1)); CLAUDE.md carries the JS mirror + D4 rule + Kraken addendum. |
| 1.1 Enums + model fields + `from_extracted` + tests | `[ ]` | **Done.** `MedCategory` (8, incl. `PLANT_PROTEIN`), `Course`, `RecipeSource`, `DishType` extended ([enums.py:16](../src/dispensa/domain/enums.py#L16)); `MappedRecipe` + dropped-category tolerance ([models.py:311](../src/dispensa/domain/models.py#L311)); `tests/test_domain_models.py`. |
| 1.2 Prompt v2 + regression test | `[ ]` | Superseded — prompt is at **v3** ([batch.py:28](../src/dispensa/ai/batch.py#L28)); promote-respects-edits test is `tests/test_editing.py` / `test_promotion.py`. |
| 1.3 `extract submit --all` → `apply` (JSON store) | `[ ]` | Superseded by the DB path (Phase 2). |
| 1.4 `review_categories.py` first version | `[ ]` | **Done** as `scripts/review_categories.py` + `app/review_categories.py` + `ai/repair.py`, with `tests/test_review_categories.py`. |
| 2.4 scripts on the DB | `[~]` | Advanced past the note: `sync ingest` **does** do on-ingest Cloudinary (D14) ([cli.py:200](../src/dispensa/cli.py#L200), [ingest.py:213](../src/dispensa/app/ingest.py#L213)). Still missing: `posts` staging writes (F8), `repair_recipe.py`. |
| 4.1 `tokens.css` + AA | `[x]` | Consistent — [frontend/css/tokens.css](../frontend/css/tokens.css) present. |
| 4.2 Scaffold §14; port browse/detail/favourites | `[ ]` | **Substantially done.** `frontend/js/{main,views/browse,views/detail,views/plan}.js` + components + libs exist; `#favourites` routes. Not done: the `state/store.js` wiring (F2). |
| 4.3 Slim `/api/recipes` + client-side search cache | `[ ]` | Slim index **exists** (`RecipeSummary`, [api_models.py](../src/dispensa/api_models.py)); **client-side cache does not** (F1). Lexical + semantic search are server-side. |
| 4.4 `#week` + `#plan` live BalancePanel | `[ ]` | `#plan` **done** — optimistic upsert → PUT → rollback, `BalancePanel`, `GapSuggestions`, `DayColumn` ([plan.js:183](../frontend/js/views/plan.js#L183)). `#week` **not built** (F3). Planner shows **Mon–Fri only** ([plan.js:19](../frontend/js/views/plan.js#L19)), a change from PLAN §17's Mon–Sun. |
| 5.1 PantryList UI + kitchen X/Y | `[ ]` | Backend **done** (`routers/pantry.py`, `domain/pantry.py`); **no `PantryList.js`**, no kitchen ratio on cards. |
| 5.2 Shopping-list view + `data/aisles.json` | `[ ]` | Endpoint **done** (`GET /plans/{week}/shopping-list`, `domain/shopping.py`); **no frontend view**; `data/aisles.json` not in tree (`data/` gitignored — unverifiable). |
| 5.3 Deploy (FastAPI Cloud + Neon) | `[ ]` | Plumbing **advanced**: `dispensa.asgi:app` composition root, `[tool.fastapi]` entrypoint, MCP OAuth (`mcp_server/auth.py`), `/api/version` with git commit. Actual deployment unverifiable from tree. |
| 6.1–6.3 Editing & manual recipes | `[ ]` | **Not started** on the API (F4). `scripts/save_custom_recipe.py` exists as a stopgap. |

**Also not in PLAN's phase board:** the entire **MCP server**
(`src/dispensa/mcp_server/` — `search_recipes` + `get_recipe` tools, JWT/OAuth
resource server, `asgi.py` mount) is built and tested but appears nowhere in
PLAN.md's phases or decisions. It is a stated product goal in CLAUDE.md.

---

## 2. MCP server — registered tools and return shapes

Server: `MCPServer("dispensa")` in [server.py:26](../src/dispensa/mcp_server/server.py#L26),
run over stdio ([__main__.py](../src/dispensa/mcp_server/__main__.py)) or mounted at
`/mcp` behind a JWT bearer verifier ([auth.py:71](../src/dispensa/mcp_server/auth.py#L71))
via `asgi.py`.

| Tool | Args | Returns | Shape |
|---|---|---|---|
| `search_recipes` | `query: str = ""`, `limit: int = 20` (capped 1–100) | `list[dict[str, Any]]` | **Summary-only.** Per hit: `code`, `title`, `dish_type`, `meal_type`, `cuisine_type`, `proteins`, `total_time`, `is_favorite`, `post_url`, `score`. `to_mcp_view` ([serializers.py:9](../src/dispensa/mcp_server/serializers.py#L9)). |
| `get_recipe` | `code: str` | `dict[str, Any] \| None` | **Full detail.** `RecipeDetail.model_dump(mode="json")` — ingredients, instructions, all tag lists, `mediterranean_categories`, times, `is_favorite`, `user_notes` ([serializers.py:37](../src/dispensa/mcp_server/serializers.py#L37)). `None` when the code is unknown. |

**Flag (F10):** `search_recipes` is the only discovery tool and it returns
summary-only rows — no ingredients, no `mediterranean_categories`, no
difficulty. Any week-planning flow over MCP must fan out to `get_recipe` per
candidate. The docstring says as much, so this is deliberate context-thrift, not
a bug; noting it because the audit asks for it.

`get_recipe` returning `None` (not an error) for an unknown code is fine but
means a hallucinated code is indistinguishable from a deleted one on the wire.

Deps are wired once per process (`@cache` on `_deps()` / `_openai_client()` —
[server.py:29](../src/dispensa/mcp_server/server.py#L29)); the recipe list is then
served from `RecipeRepository._all_cache`.

---

## 3. Sync pipeline trace

Actual command group ([cli.py:170](../src/dispensa/cli.py#L170) onward), `dispensa sync`:

```
dedupe-links → ingest → extract → status → apply → promote → embed        (+ all)
                                   └── "fetch" in the audit brief = apply ──┘
```

There is **no `fetch` command**. Downloading batch output is
`fetch_batch_output` ([batch.py:327](../src/dispensa/ai/batch.py#L327)), called
only by `sync apply`. `status` is an optional poll.

| Step | CLI cmd | App/adapter fn | Tests | Notes |
|---|---|---|---|---|
| dedupe-links | `sync dedupe-links` | `ingest.dedupe_links` | `test_sync_ingest.py:84` | Pure; dedupes a links `.txt` against `RecipeRepository` codes. |
| ingest | `sync ingest` | `ingest.ingest_food_json` / `parse_food_items` | `test_sync_ingest.py` | Independent new/caption/image flags. On-ingest Cloudinary (D14) is wired. **Does not write `posts` (F8).** **Caption-changed does not reach `extract` (F5).** |
| — | `sync backfill-images` | `backfill_images.backfill_images` | **none** | Whole-DB image repair. **No test at all** (direct or via API). |
| extract | `sync extract` | `extraction.submit_batch` → `ai.batch.create_batch` | `test_app_extraction.py`, `test_batch_submit.py` | Async; writes `data/last_batch_id.txt` + archives input JSONL. `--only-missing` excludes codes in any archived batch input **or** already extracted at `PROMPT_VERSION`. |
| status | `sync status` | `ai.batch.log_batch_status` | **none** | Thin OpenAI poll. Untested. |
| apply | `sync apply` | `extraction.apply_batch` → `fetch_batch_output` | `test_batch_apply.py`, `test_app_extraction.py` | Appends `extractions` rows only; per-line failures logged + counted, never abort. |
| promote | `sync promote` | `promotion.promote_version` → `domain.editing.promote` | `test_promotion.py` (incl. idempotence), `test_editing.py` | Dry-run by default; `--apply` writes. Skips `edited_fields ∪ PROTECTED_FIELDS`. |
| embed | `sync embed` | `embed.embed_recipes` | `test_app_embed.py` | `--changed` semantics via `document_hash` vs stored `embedding_source_hash`. Re-embeds missing/stale. |
| all | `sync all` | `sync_all.run_stages` over ingest→extract→promote→embed | `test_sync_all.py` covers **`run_stages` only** | The **CLI wiring** in `sync_all_cmd` ([cli.py:435](../src/dispensa/cli.py#L435)) — stage lambdas, dry-run/`--yes` propagation, Cloudinary/OpenAI client construction — is **untested**. Docstring itself notes `all` can't wait out the async batch. |

**Steps with no CLI command:**
- `repair_recipe.py` (PLAN §12) — never built. Only categories-only review exists.
- `review_categories` — `scripts/review_categories.py` only; no `dispensa` subcommand.
- `diff_batch` — `scripts/diff_batch.py` + `make diff` only; no `sync` subcommand (deliberate per `scripts-audit.md`, but PLAN §12 lists it as a pipeline tool).

**Untested pipeline code:**
- `app/backfill_images.py` — zero coverage.
- `ai/repair.py` (`build_category_agent`, `propose_categories`) — zero coverage; makes a live pydantic-ai call.
- `ai/batch.py::log_batch_status`, `fetch_batch_output` error branches, `recover_batch_input` — untested.
- `cli.py` — no test imports it; every Typer command is an untested wrapper.
- `storage/maintenance.py` — only `ensure_database` is exercised (conftest); `dump/restore/reset/refuse_destructive_on_prod/require_confirmation/looks_like_prod` untested.
- `instagram/` package (`_auth`, `cache_manager`, `collection`, `extractor`) — zero coverage (frozen/flagged, but still shipping).

---

## 4. Storage — multi-user readiness

`storage/_tables.py`. **No table has a household/user/tenant scope column.**

| Table | PK / unique | For multi-user, would need |
|---|---|---|
| `recipes` | `code` PK | Library is assumed global. If recipes become per-household: `code` → `(household_id, code)` or a `household_id` column + FK fan-out on `extractions`, `recipe_embeddings`, `user_state`, `planned_meals.recipe_code`. |
| `extractions` | `id` PK, FK `recipe_code` | Inherits recipe scope; no change if the library stays global. |
| `recipe_embeddings` | `recipe_code` PK | Same. |
| `posts` | `code` PK | Same (and currently unused, F8). |
| `week_plans` | **`week_start` UNIQUE** ([_tables.py:124](../src/dispensa/storage/_tables.py#L124)) | **Must change** → `UNIQUE(household_id, week_start)`. Today two households cannot both plan the same week. |
| `planned_meals` | `id` PK, FK `plan_id` | Inherits plan scope once `week_plans` is scoped. |
| `pantry_items` | `id` PK, no natural key | Add `household_id`; no constraint change but every read (`PantryRepository`) filters nothing today. |
| `user_state` | **`recipe_code` PK** ([_tables.py:156](../src/dispensa/storage/_tables.py#L156)) | **Must change** → `PRIMARY KEY(user_id, recipe_code)`. Named "user_state" but is single-user (one favourite/notes row per recipe, globally). |
| `targets` | **`category` PK** ([_tables.py:167](../src/dispensa/storage/_tables.py#L167)) | **Must change** → `PRIMARY KEY(household_id, category)`. Targets are global; PLAN §2 calls them "user-editable". |

Four constraints to migrate: `week_plans.week_start`, `user_state.recipe_code`,
`targets.category`, plus a `pantry_items` scope column. Every repository
(`plans_db`, `pantry_db`, `targets_db`, `user_state_db`) currently issues
unscoped `SELECT`s and would need a scope parameter threaded from the router →
`deps` → repo.

---

## 5. Search — embedding storage, comparison, cost

**Storage.** `recipe_embeddings` ([_tables.py:88](../src/dispensa/storage/_tables.py#L88)):
one row per recipe — `recipe_code` PK, `model`, `embedding: list[float]` in a
**JSON column** (TEXT-JSON on Postgres; **not `jsonb`, not `pgvector`**),
`embedding_source_hash` (sha256 of `recipe_document(recipe)` —
[embeddings.py:15](../src/dispensa/ai/embeddings.py#L15)), `created_at`. Model:
`text-embedding-3-small`, **1536 dims**.

**Comparison** ([recipes_db.py:364](../src/dispensa/storage/recipes_db.py#L364)):
1. `find_similar` calls `self.find(...)` → `list_all()` (process-cached) → Python facet filters → candidate `Recipe` list.
2. One `SELECT … WHERE recipe_code IN (candidate_codes)` pulls the embedding rows; each `embedding` is JSON-decoded into a Python `list[float]`.
3. `cosine_similarity` ([similarity.py:4](../src/dispensa/domain/similarity.py#L4)) — pure-Python `sum`/`zip`, no numpy — is called per candidate.
4. Sort by score desc, take `limit`. **No absolute threshold** (per CLAUDE.md).

Query embedding: 1 OpenAI `embeddings.create` call per search
([search_recipes.py:40](../src/dispensa/app/search_recipes.py#L40)).

There is **no cache for embedding vectors** (unlike `RecipeRepository._all_cache`
for recipes): every semantic query re-`SELECT`s and re-parses the JSON for the
whole candidate set.

**Cost estimate** (`recipe_document` ≈ 150–250 tokens/recipe):

| Scale | One-time embed (batches of 100) | Per query — OpenAI | Per query — server CPU (pure-Python cosine) | Vector JSON parsed/query |
|---|---|---|---|---|
| 1,000 recipes | ~0.2 M tok ≈ **$0.004**, 10 requests | 1 embed call ≈ **$4e-7** | ~1,000 × 1,536 × ~3 fp ops ≈ 4.6 M ops ≈ **0.1–0.2 s** CPython | ~1,000 rows × 1,536 floats ≈ **12 MB** raw, ~50–100 MB as Python objects |
| 5,000 recipes | ~1.0 M tok ≈ **$0.02**, 50 requests | same **$4e-7** | ~23 M ops ≈ **0.5–1.0 s** CPython | ~60 MB raw, ~250–500 MB as Python objects |

Dollar cost is negligible at both scales. The real ceiling is **per-request
latency and allocator churn**: at 5k the unfiltered semantic path parses ~5k×1536
floats from JSON and runs a Python-level dot product every call. CLAUDE.md defers
pgvector to ~10k rows; the cheaper intermediate wins (before pgvector) are a
process-level vector cache and a numpy dot product.

---

## 6. Frontend — refetch on navigation, what is cached

**Router** ([main.js:23](../frontend/js/main.js#L23)): `hashchange` → `route()` →
`view.replaceChildren()` → re-invoke the view's `render*`. Every navigation
rebuilds from scratch and re-fetches.

| View | Fetches on entry | Re-fetches on | Cached |
|---|---|---|---|
| `browse` / `favourites` ([browse.js:150](../frontend/js/views/browse.js#L150)) | `getAllRecipes(query)` + `getRecipeCounts(query)` (parallel) | every filter change, **every keystroke** (lexical), segment switch, mode toggle, **and after every favourite toggle** (`onToggleFavourite` → `refetch()`) | Nothing. `latestRequest` counter only drops stale responses. |
| `recipe/{code}` ([detail.js:21](../frontend/js/views/detail.js#L21)) | `getRecipe(code)` | — (re-fetched on every visit) | Nothing. Favourite/notes writes update local vars only. |
| `plan` ([plan.js:28](../frontend/js/views/plan.js#L28)) | `getPlan(weekStart)` then `getRecipe` for each meal code | week nav (`goToWeek` **guards re-fetch of the same week**: [plan.js:154](../frontend/js/views/plan.js#L154)); meal add/remove/portions return a fresh `PlanResponse` | `recipesByCode` Map — meal display rows, **for this mount only**; lost on navigating away. |
| footer version ([main.js:68](../frontend/js/main.js#L68)) | `getVersion()` once at startup | never | in the DOM text only |

- **No `sessionStorage` / `localStorage` / in-memory index anywhere** (grep: 0 hits).
- **`state/store.js` is imported by nothing** (F2) — the D7 store is unused; each view manages state with closures + a manual `renderAll()`.
- **Server-side** the only cache is `RecipeRepository._all_cache` (full deserialised recipe list per process, dropped on any `save`/`delete` — [recipes_db.py:198](../src/dispensa/storage/recipes_db.py#L198)).
- Consequence for PLAN 4.3: the "search stays client-side over a slim index cached per session" (D12) contract is unimplemented; the browse page is a chatty server-search UI instead.

---

## 7. Tests — coverage gaps and network

**Modules with no test coverage (direct or indirect):**
- `app/backfill_images.py`
- `ai/repair.py`
- `cli.py` (all Typer commands — thin wrappers, but the `sync all` wiring in particular, F/§3)
- `mcp_server/__main__.py` (entrypoint)
- `mcp_server/server.py::search_recipes` (the tool fn itself; `search_recipes_semantic` app fn *is* tested)
- `instagram/` — `_auth.py`, `cache_manager.py`, `collection.py`, `extractor.py` (zero `dispensa.instagram` imports in `tests/`)
- `storage/maintenance.py` — everything except `ensure_database` (`dump`/`restore`/`reset`/prod guards)
- `storage/recipes_json.py` — **imported by nothing** in `src/`, `scripts/`, or `tests/`. CLAUDE.md and PLAN §3 say it is "kept for import/export only", but `app/import_json.py` and `app/export.py` do their own JSON I/O and never touch it. Fully dead.

**Well covered:** all of `domain/` (`planning`, `pantry`, `shopping`, `editing`,
`diffing`, `proteins`, `synonyms`, `hashing`, `similarity`, `models`);
`app/` promotion/extraction/embed/diff_batch/search/review_categories/version;
every router via `tests/test_api.py`; MCP `get_recipe` + OAuth verifier;
`images/cloudinary` (SDK faked).

**Network:**
- **No test hits the internet.** OpenAI, Cloudinary, and Instagram are all faked (`_FakeOpenAI` in `test_embeddings.py` / `test_app_embed.py` / `test_batch_submit.py`; `monkeypatch.setattr(cloudinary.uploader, "upload", …)` in `test_images_cloudinary.py`).
- **Every DB test requires a live local Postgres.** `conftest.py` `postgres_engine` fixture calls `ensure_database(DATABASE_URL_TEST)` and `SQLModel.metadata.create_all` — it will connect to (and try to CREATE) a real Postgres server. This is the documented Kraken-style choice (CLAUDE.md: "test through the public use-case function against the Postgres test DB"), but it contradicts PLAN §3/§19's "storage = sqlite-tmp round-trips" and the CLAUDE.md testing rule "no real disk outside `tmp_path`". Not a bug — a doc/rule inconsistency to reconcile.

---

## 8. Dead code, TODOs, inline-silenced rules

**TODO / FIXME / XXX / HACK:** none in `src/`, `scripts/`, or `frontend/js/`.

**Inline-silenced lint rules:** none. No `# noqa`, no `# type: ignore`, no
`# ruff:` in `src/`, `scripts/`, or `tests/`. All suppression lives in
`pyproject.toml`:
- `[tool.ruff.lint].ignore` — 6 rules, each with a URL or one-line reason ([pyproject.toml:53](../pyproject.toml#L53)).
- `[tool.ruff.lint.per-file-ignores]` — 9 path globs, each with a comment justifying it ([pyproject.toml:66](../pyproject.toml#L66)).
- `[tool.mypy.overrides]` — `instagrapi.*` / `cloudinary.*` `ignore_missing_imports` (no stubs).

This section of CLAUDE.md's rules is **fully complied with** — nothing to fix.

**Dead code / dead schema:**
| Item | Status |
|---|---|
| `frontend/js/state/store.js` | Exported `createStore`; imported nowhere (F2). |
| `storage/_tables.py::PostRow` + `posts` table | Never read or written (F8). |
| `recipes.caption_hash` column | Written by `_to_row`, never read (F6). |
| `Recipe.archived` ([models.py:170](../src/dispensa/domain/models.py#L170)) | No router / app / query path references it. Reserved for Phase 6 / D15. |
| `Recipe.edited_by_user` ([models.py:172](../src/dispensa/domain/models.py#L172)) | Marked "retired by `edited_fields`" but still load-bearing in `RecipeRepository.save` (F7) — needs finishing, not deleting. |
| `scripts/import_existing.py`, `migrate_drop_user_state_fields.py`, `backfill_base_servings.py`, `backfill_authors.py` | Spent one-offs, per `docs/scripts-audit.md` §"SAFE TO DELETE". `backfill_authors.py` is the sole writer of `author_username` — confirm no future need before removing. |
| `scripts/eval_search.py` vs `scripts/dev/probe_semantic_search.py` | Overlapping search probes; `eval_search` embeds inline and ignores stored vectors (self-described "throwaway"). |
| `storage/recipes_json.py` | Imported by nothing (see §7). "Kept for import/export" per the docs, but the import/export use-cases don't use it. |

**Doc artefacts that are now misleading:**
- `docs/scripts-audit.md` — "phase 1 (read-only)" proposal; its facts (`PROMPT_VERSION` = "2", `images/` "empty placeholder", `sync` not yet built) are all stale.
- `docs/PLAN.md` Parts II/VII — `PROMPT_VERSION`, the 7-vs-8 Mediterranean category count (PLAN §2 table omits `plant_protein`; code and CLAUDE.md have 8), `#week` in Phase 4, `tests/test_architecture.py`.
- `README.md:11` — "Repo name is `cookstagram` (historical)"; the working directory is `foodiegram` and the package was renamed to `dispensa` at commit `26cc3fd`, ahead of the Phase-5 plan.
