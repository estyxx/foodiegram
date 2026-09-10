# Dispensa — Phases 9–13 (append to docs/PLAN.md Phase Board)

Derived from `docs/AUDIT.md` (commit `26cc3fd`). Each phase is one or two
Claude Code sessions. Work one checkbox at a time; green gate before commit.

Anything below that is not the current phase goes to a note, not into the
session.

---

## Decisions (continuing from D21)

| # | Decision |
|---|---|
| D22 | The unit of planning is a **meal you actually cook**, not an Instagram post. A meal slot holds a recipe code; the recipe may be `source=MANUAL` with `inspired_by=[...]` (D17). Custom recipes are first-class library entries, not overrides on a slot. |
| D23 | `set_meal` accepts a recipe code **or** an inline draft (title + ingredients + manual categories). An inline draft is saved as a MANUAL recipe on the fly, so the balance engine always works off a saved recipe. |
| D24 | `inspired_by` may point at `is_recipe=false` posts. |
| D25 | Edit protection keys off `edited_fields` only. `edited_by_user` is removed. |
| D26 | Caption change detection reads `recipes.caption_hash` vs the `caption_hash` recorded on the latest `extractions` row. `sync extract --only-missing` includes caption-changed recipes. |
| D27 | Web search: slim index fetched **once per session** and filtered client-side (D12, finally). Semantic search stays server-side. |
| D28 | Vector search: process-level cache of embeddings + numpy dot product. pgvector is deferred until >5k recipes. |
| D29 | Multi-user scope is a **household**, not a user. Recipes are one shared library. `week_plans`, `pantry_items`, `targets`, `user_state` are scoped by `household_id`. Invite-only, no signup UI. WorkOS AuthKit (already the MCP IdP) becomes the web IdP; Basic auth retired. |
| D30 | Instagram capture v1 is an iOS Shortcut posting to `/api/instagram/queue`. No Expo app; the RN Web migration is off the board. |
| D31 | Pantry items have `location: fridge \| freezer \| pantry`, optional free-text quantity and optional expiry. Names stay free-text; no canonicalisation. |
| D32 | `posts` staging table is dropped. `sync ingest` writing stubs directly is the design. |

---

## Phase 9 — Debt sweep and pipeline close-out

- [~] 9.1 Run the pipeline end to end: `sync apply` → `sync promote --apply` →
      `sync embed --changed`. Record before/after count of recipes with empty
      ingredients. Verify `db dump` / `db restore` accept the SQLAlchemy URL
      (strip `+psycopg2` before handing to `pg_dump` / `pg_restore`); add a
      test for the URL conversion.
      → Pipeline run deferred (already run 2026-08-20; only 831 empty
      `summary` fields remain — see docs/NOTES.md). `_libpq_url` already
      exists (`storage/maintenance.py`); its test was skipped by choice.
      Empty-ingredient count: 444 total / 251 `is_recipe`, unchanged.
- [x] 9.2 Finish edit tracking (D25): `RecipeRepository.save` preserves
      `edited_fields` whenever the stored set is non-empty; remove
      `edited_by_user` from model, row, and migrate the column away. Test:
      an edited recipe survives a non-promote `save()`.  (commit 0e5fb95)
- [ ] 9.3 Wire caption-changed → re-extract (D26): store `caption_hash` on
      `extractions`; `extract --only-missing` includes recipes whose
      `recipes.caption_hash` differs from their latest extraction. Test it.
      → DEFERRED: caption edits are rare; not worth the batch-pipeline
      changes now. Revisit if/when captions start changing in bulk. D26
      stays on the books. See docs/NOTES.md.
- [ ] 9.4 Delete: `frontend/js/state/store.js`, `storage/recipes_json.py`,
      `PostRow` + `posts` table (D32), `scripts/import_existing.py`,
      `migrate_drop_user_state_fields.py`, `backfill_base_servings.py`,
      `backfill_authors.py`, `docs/scripts-audit.md`. Move `schiena.html`
      out of `frontend/`.
      → The four `scripts/*.py` were already gone before this phase (removed
      in the foodiegram→dispensa rename). `frontend/schiena.html` stays put
      by owner's call — personal page, not part of dispensa, harmless as a
      static file. Everything else deleted.
- [x] 9.5 Tests for `cli.py::sync_all_cmd` wiring and for
      `storage/maintenance.py` prod guards (`looks_like_prod`,
      `refuse_destructive_on_prod`).
      → `tests/test_cli_sync_all.py` (5: stage order, dry-run propagation,
      prod guard ±`--yes`, stop-on-first-error) + `tests/test_maintenance.py`
      (9: `looks_like_prod`, `refuse_destructive_on_prod`,
      `require_confirmation`). +14 tests.
- [x] 9.6 Reconcile docs: PLAN.md checkboxes for Phases 0/1/4/5 to reality,
      `PROMPT_VERSION=3`, 8 categories, `#week` removed, a Phase entry for
      the MCP server as built, testing rule in CLAUDE.md says Postgres test DB
      (not sqlite-tmp). README repo-name line.
      → `docs/PLAN.md` phase board 0/1/4/5 marked to reality + "Phase 3.5 —
      MCP server (BUILT)" added; `PROMPT_VERSION`/8-categories/`#week`/Mon–Fri/
      import-linter/Postgres-test-DB drift fixed in PLAN.md + CLAUDE.md;
      README working-dir-vs-package line corrected, dead `recipes_json.py`
      reference dropped.
- **Done when:** library has no empty stubs from the interrupted batch; the
  three P1 findings are closed; the delete list is gone; PLAN.md matches the
  tree.
  → 9.1 pipeline run and 9.3 (caption-changed re-extract) deferred by
  owner's call (see notes above); F7 (9.2) and F8/F2/dead-code (9.4) closed;
  PLAN.md reconciled. Remaining P1 F5/F6 ride with the deferred 9.3.

## Phase 10 — Control from Claude (MCP write tools)

- [ ] 10.1 Domain: `Recipe.inspired_by: list[str]` (D17, D24). Use-case
      `save_custom_recipe(...)` that builds a MANUAL recipe with
      `m-{slug}-{rand}` code and `CategoryServing.source="manual"`. Replace
      `scripts/save_custom_recipe.py` with it. `POST /api/recipes` exposes it.
- [ ] 10.2 MCP `get_planning_context(week_start)` → one payload: meals,
      balance, oily fish, gap suggestions, targets, pantry, favourites codes.
- [ ] 10.3 MCP `set_meal(week_start, day, slot, code | draft, portions)`,
      `clear_meal`, `set_portions` — thin wrappers over the same use-cases
      `PUT /plans/{week}/meals` calls (D23).
- [ ] 10.4 MCP `save_recipe` (custom, with `inspired_by`) and
      `update_recipe(code, notes?, is_favorite?, edited fields...)`.
- [ ] 10.5 Pantry (D31): add `location`, `quantity`, `expires_on` to
      `PantryItem`; MCP `get_pantry`, `add_pantry_items`,
      `remove_pantry_items`.
- [ ] 10.6 `search_recipes` slim view gains `mediterranean_categories` and
      `difficulty` (cheap fields that stop the per-hit `get_recipe` fan-out).
      Optional `category` and `pantry_only` filters.
- **Done when:** a full week is planned in one Claude chat with no
  re-explaining: context in one call, a custom variant saved and slotted, the
  pantry updated, nothing typed twice.

## Phase 11 — Web speed and Plan UI catch-up

- [ ] 11.1 Client-side slim index (D27): fetch `/api/recipes` slim once per
      session into memory; lexical filter, facet counts and favourite toggle
      all local; one PATCH on toggle, no refetch. Measure keystroke latency
      before/after.
- [ ] 11.2 Plan view: cache `recipesByCode` across mounts; detail view reuses
      the index for header data.
- [ ] 11.3 Vector cache + numpy dot product in `find_similar` (D28).
- [ ] 11.4 Measure cold start: `/api/version` cold vs warm; check Neon
      suspend timeout and FastAPI Cloud min instances. Decide, don't guess.
- [ ] 11.5 Plan UI: "+ add" offers "my version of…" (inline draft → MANUAL
      recipe via 10.1). Decide Mon–Fri vs Mon–Sun and record it.
- [ ] 11.6 Minimal `PantryList` view (list, add, remove, location filter).
- **Done when:** browse feels instant; plan page opens without a fetch storm;
  a custom meal can be added from the web without the CLI.

## Phase 12 — Capture automation

- [ ] 12.1 `PendingLink` + `POST/GET /api/instagram/queue`, synchronous
      Cloudinary thumbnail (see `claude_ios-share-capture-plan.md` §2).
- [ ] 12.2 iOS Shortcut: share sheet → POST URL with Basic auth (D30).
- [ ] 12.3 GitHub Actions hourly caption sync: cookies secret, PATCH caption
      onto the stub, mark processed, fail loudly.
- [ ] 12.4 GitHub Actions weekly: `extract` → `apply` → `promote --apply` →
      `embed --changed`.
- **Done when:** a link shared from the phone becomes a promoted, embedded
  recipe with no laptop involved.

## Phase 13 — Household (multi-user)

- [ ] 13.1 `households` table; `household_id` on `week_plans`,
      `pantry_items`, `targets`, `user_state`. Constraints:
      `UNIQUE(household_id, week_start)`, `PK(household_id, recipe_code)`,
      `PK(household_id, category)`. Migration seeds one household from
      existing rows.
- [ ] 13.2 Thread `household_id` router → deps → repositories. Every
      scoped repo query takes it; no unscoped reads remain (test).
- [ ] 13.3 MCP: household resolved from the JWT.
- [ ] 13.4 Web: WorkOS AuthKit login, Basic auth removed, invite via
      WorkOS org membership.
- **Done when:** two households plan the same week against the same library
  without seeing each other.

---

## Kickoff prompt — Phase 9 (paste into Claude Code, plan mode)

```
Read CLAUDE.md, docs/AUDIT.md, and docs/PLAN.md Phase 9 and decisions
D22–D32. Derive reality from the tree, not the docs.

We are doing Phase 9 only. Restate the goal of 9.1 in one sentence, then
plan it: which commands to run, in what order, and what count you'll report
before and after (recipes with empty ingredients). Do not run anything that
writes until I confirm.

After 9.1, continue 9.2 → 9.6 one item at a time. For each: plan, I approve,
you edit, then run `ruff check --fix . && ruff format . && mypy . && pytest
&& lint-imports`. Red means not done.

Constraints:
- Keyword-only args, use-cases as module-level functions, no
  `from __future__ import annotations`.
- 9.4 is deletion only. If a deleted script turns out to be referenced
  anywhere, stop and tell me instead of keeping it.
- Nothing from Phase 10+ enters this session. If you notice something
  worth doing, write it to docs/NOTES.md and move on.
- Do not commit; tell me when an item is green and I will.
```
