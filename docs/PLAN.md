# Dispensa plan

Dispensa is a personal Mediterranean-diet recipe library and weekly meal planner.
It ingests saved Instagram posts, extracts structured recipe data from the caption
with OpenAI, exposes the library to Claude through an MCP server for meal planning,
and serves a browsable site for searching recipes and planning a week of meals. It
is a solo hobby project for personal use, ADHD-friendly by design.

This is the single planning document: the product, the roadmap and the reasoning.
Architecture rules and coding conventions live in `CLAUDE.md`; this file does not
repeat them. Roadmap items use checkboxes: `[x]` done, `[ ]` still to do. A heading marked
(in progress) or (not started) flags where an area stands at a glance.

## Contents

1. [Product](#product)
2. [How it works](#how-it-works)
3. [Status at a glance](#status-at-a-glance)
4. [Roadmap](#roadmap)
5. [What's next](#whats-next)
6. [Open questions](#open-questions)
7. [Decision log](#decision-log)
8. [Reference](#reference)

## Product

### What it is

A library of around 1,180 recipes (mostly Italian), each extracted from a saved
Instagram caption, plus manually added recipes. The signature feature is a live,
colour-coded weekly balance panel that tracks eight protein categories against
Mediterranean targets: adding or removing a recipe from the week moves the bars in
real time and suggests gap-fillers. Around it sit browse and search, pantry-lite
awareness, a shopping list, cooking mode, and an installable phone app. A back-
exercise tracker lives alongside as its own small context.

### The Mediterranean engine

Eight tracked categories, each with one fixed colour, used identically everywhere
(balance panel, day chips, recipe badges). Cooler means eat more, warmer means go
easy. Colour is never the only signal: it is always paired with a text label or icon.

| Category | Weekly target (default, user-editable) |
|---|---|
| fish | 2+ (aim for at least one oily) |
| legumes | 2+ |
| plant_protein | 1+ (tofu, tempeh, edamame, seitan; not legumes) |
| poultry | 0-2 |
| eggs | 2-4 |
| dairy | 0-7 (soft) |
| red_meat | 0-1 |
| processed_meat | 0-1 |

Counting rules:

- A recipe can count toward several categories (carbonara counts eggs, processed
  meat and dairy).
- Cured and processed meats always map to processed_meat, at full weight when they
  are the backbone of the dish.
- Count a category only when it is substantial (roughly 30g per portion or central
  to the dish). Grated parmesan to finish a pasta does not count dairy.
- Plant categories are floors with no ceiling, so they never read "over"; animal
  categories keep a ceiling and lose any floor that would nudge toward more meat
  (the diet-pyramid targets, after Bach-Faig et al. 2011).
- Balance counts slots, not portions. Cooking fish once and eating it twice means
  planning it on two days, which is two fish servings. `portions` is only for
  scaling and the shopping list.

## How it works

### Layering

```
routers/api -> app -> storage | ai | images | instagram -> domain
```

Dependencies point inward only, enforced by import-linter (four contracts). The
domain is pure: no I/O, no SDKs, no clock. Use-cases are module-level functions in
`app/`, the only layer that combines siblings. SQLModel rows never leave `storage/`;
repositories accept and return domain models. Everything serialised is a frozen
Pydantic v2 model.

### The recipe data lifecycle

Two stores. **Local Postgres is the ingest and extraction workshop; Neon is prod
and the source of truth for everything the user writes** (plans, pantry, targets,
favourites, notes, manual recipes).

Extraction is append-only and asynchronous. `extractions` rows are immutable LLM
outputs stamped with the prompt version and model; `recipes` is the mutable
canonical state. `promote()` is the only path between them and never overwrites a
field the user has edited (`edited_fields`). Semantic search needs its own step:
`embed` re-embeds only recipes whose extracted document changed.

The historical bulk path runs locally over a downloaded `food.json`:

```
ingest -> extract (OpenAI Batch, async) -> apply -> promote -> embed --changed
```

Recipe improvements then move to Neon with `sync push`, which inserts new Instagram
recipes and updates only fields Neon has not edited. It never deletes and never
touches plans, pantry, notes or manual recipes.

### Capture (the in-app queue)

The newer path replaces the local scripts for day-to-day capture. Share an Instagram
link to the queue, paste its caption, launch an OpenAI batch, and import the finished
recipes, all from the app against Neon. Batch state lives in the `batch_runs` table,
not on disk, so a disk-less prod process can submit a batch in one request and apply
it in another. The recipe is born on import, when the batch finishes, which keeps
browse clean while a post is still extracting.

## Status at a glance

The core app is in daily use: browse and search (keyword plus semantic), weekly
planning with the live balance panel, pantry and shopping list, recipe editing,
cooking mode, and an installable PWA. The MCP server is deployed behind OAuth so
Claude can read the library and write plans. The data pipeline, the safety net (CI,
weekly Neon backup, migrations) and the in-app capture queue are all in place. What
remains is mostly the recipe-edit UI, the identity layer (per-household login), and
a few capture conveniences.

## Roadmap

Grouped by area rather than by the original phase numbers, which accumulated across
several planning rounds. Done work is kept so the history of what was built stays
legible.

### Foundations: domain, pipeline, storage

- [x] Pure domain layer: enums (8 Mediterranean categories including plant_protein),
  models, `promote()` with the edited-fields rule (the anchor test of the codebase),
  diffing, planning, pantry and shopping, synonyms.
- [x] DDD-lite package layout by pure moves; import-linter contracts replace the old
  architecture test.
- [x] Postgres everywhere (SQLite removed): hand-written repositories per aggregate,
  SQLModel rows private to `storage/`.
- [x] Append-only `extractions`; `promote` merges into `recipes` preserving user edits;
  `diff_batch` answers "I changed the prompt, what changed?".
- [x] Local data loaded and round-tripped; extraction history backfilled; a re-promote
  changes nothing (idempotence proven).
- [ ] Debt sweep: edit-tracking finished, dead code and the `posts` staging table
  removed, CLI and prod-guard tests added. Deferred by choice: the caption-changed
  re-extract wiring (D26, caption edits are rare) and a one-off pipeline run to fill
  ~831 empty `summary` fields.

### Planning engine and API

- [x] `domain/planning.py`: week balance (multi-category, slot-not-portion,
  under/ok/over), oily-fish count, gap suggestions ranked by confidence then
  favourites, all pure and tested.
- [x] Plan, pantry and targets endpoints; `GET /api/plans/{week}` returns plan,
  balance and suggestions in one payload so the frontend does no balance math.
- [x] A meal slot holds one or more dishes (D34); moving a dish across days and across
  weeks.

### Claude and the MCP server

- [x] MCP server over stdio or mounted at `/mcp` behind a JWT/OAuth verifier, with a
  subject allow-list.
- [x] Read tools (`search_recipes`, `get_recipe`, `get_planning_context`) and write
  tools (`add_meal`, `clear_meal`, `set_portions`, `save_recipe`, `update_recipe`,
  `add`/`remove_pantry_items`), all thin wrappers over the same use-cases the API
  calls.

### Web app and speed

- [x] Design tokens and the component system (no-build ES modules, `// @ts-check`,
  pure function components, `textContent` only, a11y as a review gate).
- [x] Browse, recipe detail ("split workbench" redesign), plan page ("Plan v5"),
  favourites; cooking mode with step timers that hand off to the iPhone Clock.
- [x] Client-side session index for instant lexical search, facet counts and favourite
  toggles; semantic search stays server-side; one shared numpy embedding matrix.
- Note: `#week` (a home dashboard) was never built and is deferred; the planner is
  Mon-Fri with a weekend toggle (D33).

### Weekly loop: shopping and pantry

- [x] Shopping-list page from the plan: the week's not-in-pantry ingredients grouped by
  aisle, tick-to-strike persisted per device, offline via the service worker.
- [x] Aisle map built from the library's own ingredient words.
- [x] Pantry page (list by location, add, remove); cross-language synonym pairs for the
  common pantry words.
- [x] Installable PWA: manifest, icons, service worker for the app shell and the current
  shopping list.
- [x] Diet-pyramid targets with optional ceilings (plant floors, animal ceilings).

### Editing and manual recipes (in progress)

- [x] Widen the recipe PATCH and `edited_fields` to cover title, ingredients,
  instructions, times, difficulty, categories with servings and the archived flag;
  MCP `update_recipe` gains the same.
- [x] Revert one edited field to its latest extracted value.
- [x] Archive an Instagram save, delete a manual recipe; archived recipes leave browse,
  search, semantic ranking and gap suggestions but still render on a past plan.
- [x] Edit the recipe from its page: an edit dialog (reusing the custom-recipe
  form) over the widened PATCH, with a per-field "edited" marker; verbatim content
  marked with the recipe's `language`, which is now its own field (defaulting to
  Italian, editable in the dialog).
- [ ] Paste a recipe: save pasted text at once as a manual recipe "waiting for
  extraction", filled in by the next batch run; and an optional "extract now" button,
  only if the wait proves to hurt.

### Capture queue and extraction

The in-app queue, which supersedes the earlier scripted capture plans.

- [x] `pending_links` table and the queue endpoints; the `#queue` page with per-item
  caption paste.
- [x] Launch a batch for the ready items against Neon, import the finished batch into
  recipes, with launch/import buttons on the queue page. Batch state in the DB. This
  reverses the old "extraction never runs against Neon" rule (D56).
- [ ] iOS Shortcut: share sheet to `POST /api/instagram/queue`, so capture needs no
  laptop.
- [ ] Retire the local scripts once the queue is in daily use (keep `export` and
  `db dump`). The first real extraction against Neon is still the owner's to run,
  under the spend cap.

### Back exercises (in progress)

A separate context (`body`) with its own import contract, page and per-user data,
sharing only the login.

- [x] Isolate the exercise domain so it imports nothing from the food domain.
- [x] Stable exercise ids: move the routine into one tracked data file with an id per
  exercise so renaming an exercise keeps its history. Now unblocked by migrations.
- [ ] A month view on the Progressi screen: days done per week for the last eight weeks.

### Safety net: CI, backups, migrations

- [x] CI runs the full gate on every push and pull request.
- [x] Weekly Neon backup in a separate private repo; a restore drill proven.
- [x] Health endpoints for uptime monitoring that let Neon sleep.
- [x] Date-based version plus the deployed commit in the footer.
- [x] Alembic migrations with a baseline matching the models; `init_db` runs migrations
  at startup and adopts a pre-Alembic database by stamping it at the baseline (no
  manual prod step). DDL now lives in migrations, not in `create_all`.

### Identity: one household per person (not started)

The biggest remaining block.

- [ ] `households` and `users`; a migration seeds the owner's household owning every
  existing row; a CLI command adds a user with a household of one and default targets.
- [ ] Web login with WorkOS AuthKit (already the MCP identity provider); Basic auth stays
  behind a setting for one release as the way back.
- [ ] Scope the data by `household_id` (`week_plans`, `pantry_items`, `targets`,
  `user_state`), threaded router to deps to repositories, with no unscoped reads left.
- [ ] MCP resolves the user from the token; the allow-list becomes the `users` table.
- [ ] Download-my-data export and account removal.

The recipe library stays shared (one library); only plans, pantry, targets,
favourites and notes become per-household, so two people can share a household later
by pointing at the same row, with no membership table or sharing UI now.

### Deferred and someday

- [ ] AI companion: expiry nudges, a taste profile that ranks gap suggestions, a
  "draft my week" agent. Only after several weeks of real use; not designed now.
- [ ] pgvector (semantic search uses JSON embeddings plus Python cosine until ~10k rows).
- [ ] A native shell (Capacitor around the same web code) until a share-sheet or
  notification need is real. React Native is off the board.
- [ ] Screenshot or OCR capture: capture is link plus pasted caption only.
- [ ] Hourly caption sync in GitHub Actions (dropped: it scripts a flagged account from
  datacenter addresses).
- [ ] A home region for the app: FastAPI Cloud (us-east-1) and Neon (London) are on
  opposite sides of the Atlantic, so every query pays the round trip. Decision: wait
  for a European FastAPI Cloud region, then move the app next to Neon.

## What's next

In priority order, the first actionable items:

1. **Paste a recipe** (editing): save pasted text at once as a manual recipe
   "waiting for extraction", filled in by the next batch run.
2. **A month view on Progressi** (back exercises): days done per week for the last
   eight weeks, now that the log is keyed by stable ids.
3. **Identity**, the largest piece, when there is appetite for it: the `households`
   and `users` tables and their migration first, then WorkOS web login.

## Open questions

- The synonym layer is a hand-maintained cross-language workaround, and the shopping
  list mixes languages because the canonical name is an arbitrary alphabetical pick.
  The real fix is a canonical ingredient identity (a stable id per ingredient,
  rendered in the chosen interface language) rather than string aliasing. Worth doing
  when interface language or i18n is tackled.
- A custom domain name: decide when the home-region move happens, not before.
- Plan builder, from the early design exploration: whether a slot can hold a free
  "note" meal with no recipe, and how far the balance should nudge rather than just
  report. Open, low priority.

## Decision log

The running list, in order. Where a later decision supersedes an earlier one the
earlier entry is kept and marked, because the reasoning still matters.

| # | Decision |
|---|---|
| D1 | Deploy on FastAPI Cloud: one deploy ships API plus frontend; the filesystem is ephemeral, nothing mutable on disk in prod. |
| D2 | The database is the single source of truth for recipes; the deploy artifact is code only. |
| D3 | Two-entity model: append-only `extractions` versus mutable `recipes`; `promote()` is the only path and never overwrites user-edited fields. |
| D4 | ORM is SQLModel, one codebase for local and Neon. (Updated: Alembic migrations now own the schema; `create_all` at startup is retired, D38.) |
| D5 | pydantic-ai for single-recipe repair, category review and paste-to-recipe; the OpenAI Batch API stays the bulk path. |
| D6 | Full re-extraction with a richer prompt adding categories and course. (Superseded: the prompt is now at version 3, which also adds plant_protein and summary.) |
| D7 | Frontend is no-build vanilla ES modules, pure function components, JSDoc plus `// @ts-check`; TypeScript is the only dev dependency. |
| D8 | Pantry-lite: name plus staple/fresh plus optional expiry; no quantities or depletion until real use proves otherwise. (Extended by D31.) |
| D9 | DDD-lite layering, domain pure, enforced by import-linter rather than a bespoke test. |
| D10 | JSON files demote to a pipeline artifact and backup via a private data repo. |
| D11 | Recipes are keyed by `code`: the Instagram shortcode, or `m-{slug}-{rand}` for manual recipes; `pk`/`post_url`/`caption` become nullable. |
| D12 | Search stays client-side over a slim index cached per session; no full-text search. (Realised in D27.) |
| D13 | Auth is HTTP Basic over everything, disabled when unset for local dev; no login UI. (To be replaced by D29/D43.) |
| D14 | Thumbnails are fetched to Cloudinary at ingest while the Instagram CDN URLs are fresh, because they expire. |
| D15 | `is_recipe=false` posts are normal recipe rows, shown only in an inspiration shelf and excluded from planner suggestions. |
| D16 | Deferred with the door open: recipe variants, vision on photo-only posts, a goals screen, backup automation, the AI layer. |
| D17 | Manual recipes may record `inspired_by` codes; they are first-class library entries, not slot overrides. |
| D22 | The unit of planning is a meal you cook, not an Instagram post; a slot holds a recipe code. |
| D23 | A meal can be set from a code or an inline draft, which is saved as a manual recipe so the balance always works off a saved recipe. |
| D24 | `inspired_by` may point at `is_recipe=false` posts. |
| D25 | Edit protection keys off `edited_fields` only; `edited_by_user` is removed. |
| D26 | Caption-change detection compares `recipes.caption_hash` to the latest extraction's. (Deferred: caption edits are rare.) |
| D27 | The slim index is fetched once per session and filtered client-side; semantic search stays server-side. |
| D28 | Vector search uses a process-level numpy matrix of embeddings; pgvector deferred until many thousands of recipes. |
| D29 | Multi-user scope is a household, not a user; the recipe library is shared, other data is per-household; WorkOS becomes the web identity provider and Basic auth retires. |
| D30 | Instagram capture is an iOS Shortcut posting a shared link to a queue; no Expo app, no React Native. |
| D31 | Pantry items gain a location (fridge, freezer, pantry), optional free-text quantity and optional expiry; names stay free text. |
| D32 | The `posts` staging table is dropped; `sync ingest` writes recipe stubs directly. |
| D33 | The plan page shows Mon-Fri by default with a remembered weekend toggle; plans and balance always cover all seven days. |
| D34 | A meal slot holds one or more dishes, each its own row, each counting toward the balance; `add_meal` adds rather than replaces. |
| D35 | Neon is the source of truth for everything the user writes; local is the workshop; `sync push` moves only recipe improvements, never deleting. |
| D36 | A weekly Neon backup lives in a separate private repo. |
| D37 | CI runs the full gate on every push and pull request. |
| D38 | Ordered migrations (Alembic) replace DDL at startup; the baseline matches the models and existing databases are adopted by stamping. |
| D39 | No bounded-context re-slice; only `body` and `identity` get their own import contract on top of the layer contracts. |
| D40 | The phone app is the web app installed (PWA); Capacitor and TestFlight stay deferred. |
| D41 | The shopping list ships before the pantry page; the list is derived server-side each load, ticks kept per device; the aisle map is built from the library. |
| D42 | Recipe editing widens the existing PATCH and `edited_fields`; revert drops a field and re-applies the latest extraction; no second override table. |
| D43 | Identity first, one household per person; each user gets a household of one; users are added by hand; Basic auth stays behind a setting for one release. |
| D44 | MCP accepts only allow-listed token subjects now, the `users` table once identity exists. |
| D45 | The hourly Instagram caption sync is dropped; capture becomes paste-the-caption. |
| D46 | Back exercises are a separate `body` part: own contract, page and data, shared login and deploy; not rebuilt inside the SPA. |
| D47 | Monitoring must let Neon sleep: a shallow health endpoint for the uptime ping, a deep check once a day. |
| D48 | Split a large file only in the commit before the next feature that touches it; pure JS modules get `node --test`. |
| D49 | Pasted recipes are extracted in batches; a paste is saved at once as a manual recipe "waiting for extraction". |
| D50 | Balance targets follow the Mediterranean pyramid: plant categories are floors with no ceiling, animal categories keep a ceiling. |
| D51 | Version is a date-based number plus the deployed commit, shown in the footer; the commit comes from the platform at run time, never a guessed hash. |
| D52 | The free installable PWA is the everyday app; a native shell is the only paid step and stays deferred; capture is link-only. |
| D53 | Capture needs no Instagram login: a shared post link is public, so the queue takes the bare URL; full captions are pasted. |
| D54 | The in-app capture queue (a `pending_links` table and a `#queue` page) replaces the scripts; no instagrapi, no laptop. |
| D55 | The full caption is pasted per post, not scraped; one paste per queue item replaces the whole export. |
| D56 | Extraction runs from the app against Neon (the queue flow), reversing the earlier local-only rule; the recipe is born on import. |

## Reference

Condensed specifications. The code is the source of truth; these capture intent and
the decisions behind the shapes.

### Domain and data

- **Enums** (`domain/enums.py`): `MedCategory` (8 values), `Course` (Italian meal
  structure), `RecipeSource` (instagram, manual), plus meal/dish/cuisine/difficulty,
  all `StrEnum` with an `UNKNOWN` fallback.
- **Models** (`domain/models.py`, frozen Pydantic): `Recipe` keyed by `code`, with
  `mediterranean_categories: list[CategoryServing]`, `edited_fields: frozenset[str]`,
  `archived`, nullable Instagram fields; `CategoryServing` (category, servings 1.0 or
  0.5, `is_oily_fish`, source); `Extraction` (immutable, with prompt version, model,
  kind, payload); `ExtractedRecipe` (the LLM output shape).
- **Editing** (`domain/editing.py`): `PROTECTED_FIELDS` that `promote()` never touches
  (identity, media, caption, `edited_fields`, archived); `promote(current, extraction)`
  takes every extracted field unless it is edited or protected, stamping provenance;
  `apply_user_edit` records a hand edit; `revert_field` undoes one; `apply_push` for
  the local-to-Neon overlay. The anchor test: an edited field survives a re-promote.
- **Planning** (`domain/planning.py`): `WeekPlan` (Monday-validated), `PlannedMeal`,
  `CategoryTarget` (min, optional max), `CategoryStatus` (planned, target, under/ok/
  over), `week_balance`, `oily_fish_count`, `gap_suggestions`.
- **Pantry and shopping** (`domain/pantry.py`, `domain/shopping.py`): `PantryItem`
  (name, location, quantity, expiry), `kitchen_match` (naive synonym-expanded
  substring match), `shopping_list` (strip quantities, canonicalise, group by aisle,
  unknown to "altro").

### Prompt and extraction

The extraction prompt lives in `ai/prompts/extract_recipe_details.txt`;
`PROMPT_VERSION` (currently 3) lives in `ai/batch.py` and is bumped when the prompt
changes so re-extracted rows are distinguishable. The prompt pins the eight
Mediterranean categories with explicit Italian ingredient mappings and the
substantial-component rule, and the Italian course structure. The extraction model is
a reasoning model that rejects `temperature`; determinism comes from low reasoning
effort. Output is strict JSON validated through the Pydantic model, never hand-parsed.

### Shipped feature designs

Two features were worked out in detail before building and have since shipped; the
full design notes are in git history if ever needed.

- **Browse filters**: a shared canonical protein name (so "is this a recipe" and the
  protein facet agree), the protein-category facet, multi-ingredient chip search, and
  the quiet command bar. All server-side `find()` plus the client index.
- **Plan builder and custom recipes**: the balance panel with day columns, inline
  "my version of" drafts saved as manual recipes, and the custom-recipe dialog.

### Engineering follow-ups and known debt

- Several large files (`cli.py`, `storage/recipes_db.py`, the recipes router,
  `api_models.py`) are past the ~200-line smell. Split by responsibility in the commit
  before the next feature that touches them, not as standalone churn (D48).
- The synonym layer does not scale cleanly (see the open question); revisit with i18n.
- Re-run the restore drill after each schema change: restore the latest Neon dump into
  a throwaway Postgres container and check the row counts.
- `_libpq_url` (`storage/maintenance.py`) still has no direct test; it is exercised by
  `db dump`/`restore` and works.
- A `DELETE /plans/{week}/meals/{id}` still calls the repository directly rather than a
  use-case; fold it into `app/plan_meals` if that router is touched again.
- The deferred caption-changed re-extract (D26) leaves `recipes.caption_hash`
  write-only for now.
