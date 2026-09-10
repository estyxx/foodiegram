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
