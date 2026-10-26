# NOTES — out-of-phase observations

Things noticed while working a phase that belong to a later one. Not acted on here.

## From Phase 9.1 (pipeline close-out)

- **831 recipes have an empty `summary`** that their latest v3 extraction would
  fill. `sync promote --version 3 --apply` promotes only `summary` on these
  (dry-run: `considered=924 changed=831 promoted=0 preserved_fields=0`); nothing
  else diffs. `recipe_document()` includes `summary`
  (`ai/embeddings.py:26`), so `sync embed` then re-embeds those ~831. User chose
  to defer this run — pipeline otherwise complete (extractions applied, ingredients
  populated, `embed` dry-run `needs=0`, `extract --only-missing` submits 0).
- **4 `is_recipe=true` recipes whose v3 extraction returned `ingredients: []`**:
  `CaKY7gpoZUK` (Vegan Plum Cake), `B1WowmKIULV` (Involtini di melanzane),
  `Ci2m1VENCCG` (Pumpkin buns), `CstmeLIICOl` (Overnight focaccia). Model
  classified them as recipes but pulled no ingredients. Needs targeted
  re-extraction (`sync extract --all --codes …`), not promote. Phase 9.3 or later.
- **247 `is_recipe=true` recipes with empty ingredients and no caption ≥80 chars**
  (`prompt_version` NULL or `2`). Nothing to extract from; they predate the v3
  batch. Empty-ingredient count is 444 total / 251 `is_recipe`; these 247 + the 4
  above + 192 `is_recipe=false` non-recipes account for it. Left as-is.
- **`_libpq_url` (`storage/maintenance.py:79`) still has no test.** 9.1 asked for
  one; user chose to skip. The function itself is in use by `db dump` / `db
  restore` and works.

## From Phase 9.2 (edit tracking)

- **Local test-infra debt, not code:** on this machine `pytest` shows two
  failures that also fail on untouched `main` —
  `test_promotion.py::test_promote_counts_extractions_without_a_recipe` needs a
  superuser test role (`SET session_replication_role = replica` is denied to the
  `dispensa` role), and `test_storage_db.py::test_recipe_round_trips_fully` needs
  the PG session timezone to be UTC (local server is `Europe/London`; passes with
  `PGOPTIONS="-c timezone=UTC"`). CI presumably has both. Worth fixing the local
  setup or the fixtures so the green gate is honest here.

## From Phase 9.3 (caption-changed re-extract) — DEFERRED

- D26 not implemented. Caption edits are rare; the change touched the batch
  pipeline (new `extractions.caption_hash` column stamped at apply time from the
  archived batch input, hash-aware submit dedup to avoid re-extracting the
  ~900-recipe pre-D26 backlog). Plan sketch is in this session's history if
  picked up later. `recipes.caption_hash` column remains write-only (AUDIT F6).

## From Phase 10.3 / 10.4 (MCP write tools)

- **PUT `/api/plans/{week}/meals` behaviour changed.** It now goes through
  `app/plan_meals.set_meal`, so an unknown `recipe_code` is 404 (was silently
  stored) and a `day` outside Mon..Sun of the week or `portions < 1` is 422.
  The web UI only slots real codes from the current week, so it should not
  notice.
- **DELETE `/api/plans/{week}/meals/{id}` still calls the repository
  directly.** It is id-keyed and has no MCP twin (`clear_meal` is keyed by
  day+slot because the MCP meal view carries no id). Left as is; fold it into
  `app/plan_meals` if the router is touched again.
- **`RecipeCreate.instructions` is required**, so a `set_meal` draft must send
  `instructions: []`. D23 names only title + ingredients + categories. Making
  it default to `[]` would loosen POST too; owner's call.
- **`inspired_by` codes are not checked to exist** (neither by POST nor by
  `save_recipe`). A typo leaves a dangling reference.
- **`get_recipe` still returns `None` for an unknown code.** It is a read
  tool, and the brief's raise-don't-return-None rule was for writes. Worth
  aligning so the model gets a message instead of `null`.
- **`update_recipe(user_notes="")` stores `""`, not NULL**, same as PATCH.
  Harmless, but it is two spellings of "no notes".
- **The deployed MCP endpoint can now write.** `asgi.py` mounts the same
  `mcp` instance behind WorkOS OAuth, so these tools reach Neon in prod.
- **Local test infra:** the `test_storage_db` timezone failure goes away
  when the cluster default is UTC (`ALTER DATABASE template1 SET timezone TO
  'UTC'` before the test DB is created). Only the superuser one remains.
- **Prod `targets` has 7 rows; `plant_protein` is missing.** `DEFAULT_TARGETS`
  has 8, but `_seed_targets` only seeds an empty table, and prod was seeded
  before plant_protein existed. So the balance (web and MCP) never grades
  plant_protein. Needs an additive, idempotent insert of the missing default
  row(s) on Neon.
- **Stale recipe cache across repositories (fixed).** `RecipeRepository.list_all`
  cached per instance and only the saving instance invalidated, so a recipe
  saved via MCP was invisible to the web app's balance (counted 0) until a
  restart. The cache is now keyed by `(count, max(updated_at))` on `recipes`,
  one cheap query per `list_all`. This relies on every write going through
  `save`/`delete` (true today); a raw SQL `UPDATE recipes` that skips
  `updated_at` would not be noticed.
