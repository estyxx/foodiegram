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
- **Prod `targets` had 7 rows; `plant_protein` was missing (fixed).**
  `_seed_targets` only seeded an empty table, and prod was seeded before
  plant_protein existed. It now inserts each missing default category on
  every `init_db` (startup), never touching existing rows, so prod gains
  plant_protein (2-3, the placeholder in `DEFAULT_TARGETS`) on the next deploy.
- **Stale recipe cache across repositories (fixed).** `RecipeRepository.list_all`
  cached per instance and only the saving instance invalidated, so a recipe
  saved via MCP was invisible to the web app's balance (counted 0) until a
  restart. The cache is now keyed by `(count, max(updated_at))` on `recipes`,
  one cheap query per `list_all`. This relies on every write going through
  `save`/`delete` (true today); a raw SQL `UPDATE recipes` that skips
  `updated_at` would not be noticed.

## From Phase 10.5 (pantry)

- **`kind` (staple/fresh) stays alongside `location`.** D31 added location
  without retiring kind; they overlap (fresh ≈ fridge) but answer different
  questions. Revisit if `kind` ends up unused once the PantryList UI (11.6)
  exists.
- **No pantry update tool.** Changing a quantity or expiry is remove + add.
  Fine for v1; an `update_pantry_item` is cheap if the live test asks for it.
- **Adding does not merge by name.** Two "ceci" rows can coexist (one in the
  fridge, one tinned in the pantry), which is intended; names stay free-text
  per D31.

## From Phase 10.6 (search fields and filters)

- **The synonym layer has no eggs ↔ uova pair.** A pantry "eggs" does not
  match an ingredient line "2 uova" (chickpeas ↔ ceci does). This affects
  `pantry_have` / `pantry_only`, the shopping list and kitchen_match alike.
  Worth an audit of `domain/synonyms.py` against the most common pantry
  words in both languages.
- **The slim view's new fields also show in plan `suggestions`.** `to_mcp_view`
  is shared, so gap suggestions in `get_planning_context` and the write tools
  now carry `difficulty` and `mediterranean_categories` too: a few more tokens
  per suggestion, and one less reason to call `get_recipe`.

## From Phase 11.1 (client-side index)

- **The 200 ms search debounce is now most of the latency.** Local filtering
  takes ~6 ms; the debounce was sized for a network round trip. Dropping it
  for lexical mode (keeping it for AI mode, which still calls the server)
  would make typing feel instant. Small change in `SearchBar.js`, not done
  here.
- **Index size.** 2.4 MB raw / 305 KB gzip for 1,300 synthetic recipes;
  `search_text` (full captions) is most of it. Real captions compress worse
  than the synthetic ones. If it hurts on mobile, captions could leave the
  lexical match (a behaviour change vs `find()`), or the index could be
  cached with an ETag.
- **New recipes appear on reload.** The index is per session (D27), so a
  recipe saved from Claude mid-session is missing from Browse until the page
  reloads. The plan view and detail view read live, so they are unaffected.
- **No JS test runner.** `localFilter.js` parity with `find()` was checked by
  a one-off script against a running server (34 combos). `node --test` would
  run a pure-module test with no dependency if we want it in the gate.
- **`#plan` search still hits the server per keystroke** (`getRecipes` in
  `plan.js`); that is 11.2's territory.

## From Phase 11.5 (my version of… / weekend toggle)

- **Picker titles truncate hard in the Mon–Fri columns.** A wide category
  chip (PLANT PROTEIN) leaves a few characters of title ("Me…"). Pre-dates
  11.5; the rows are as wide as before. Wrapping the title or dropping the
  chip text to a dot in narrow columns would fix it.
- **A recipe saved from the plan page is missing from Browse until reload**,
  same as one saved from Claude (the session index, D27). The plan page shows
  it because it keeps the saved recipe's display itself.
