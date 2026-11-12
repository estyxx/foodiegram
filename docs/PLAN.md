# Dispensa roadmap

A personal Mediterranean-diet recipe library and weekly meal planner. It ingests
saved Instagram posts, extracts structured recipe data with OpenAI, exposes the
library to Claude through an MCP server for meal planning, and serves a browsable
site for searching recipes and planning a week of meals. Solo hobby project,
personal use, ADHD-friendly by design.

Architecture and conventions live in `CLAUDE.md`. This file is the roadmap: what
is built, what is next, and the decisions that shaped it.

## Architecture in one line

```
routers/api -> app -> storage | ai | images | instagram -> domain
```

Dependencies point inward only, enforced by import-linter. The domain is pure (no
I/O, no SDKs). Use-cases are module-level functions in `app/`, the only layer that
combines siblings. SQLModel rows never leave `storage/`; repositories accept and
return domain models. Data crosses three validation boundaries (Instagram SDK, LLM
JSON, persisted rows), so everything serialised is a frozen Pydantic v2 model.

## Status

The core app is in daily use: browse and search (keyword plus semantic), weekly
planning with a live Mediterranean-balance panel, pantry and shopping list, recipe
editing, an installable PWA, and a back-exercise page kept as its own context. The
MCP server is deployed behind OAuth so Claude can read the library and write plans.

Recent work:

- In-app capture queue with batch extraction against Neon. Share a link, paste the
  caption, launch an OpenAI batch, import the finished recipes. No local sync step.
- Batch state lives in the database (`batch_runs`), not on disk, so a disk-less
  prod process can submit a batch in one request and apply it in another.
- Alembic migrations with a baseline matching the models. `init_db` runs migrations
  at startup and adopts a pre-Alembic database by stamping it at the baseline.
- Recipe editing widened through the existing PATCH and `edited_fields`, with a
  per-field revert. Archived saves stay out of browse, search and suggestions.
- Diet-pyramid balance targets: plant categories are floors with no ceiling.

## Next

In rough priority order. Each item lands behind the green gate, one at a time.

- **Recipe edit UI.** Edit in place on the recipe page, per-field "edited" marker,
  save through the existing PATCH. Needs a per-recipe `language` field first, so
  verbatim Italian text can be marked `lang="it"` without mislabelling English.
- **Stable exercise ids.** Move the routine into one tracked data file with an id
  per exercise; the log stores the id so renaming an exercise keeps its history.
  Then a month view on the Progressi screen. Depends on migrations (done).
- **Identity, one household per person.** `households` and `users`, data scoped by
  `household_id`, web login with WorkOS AuthKit, MCP resolving the user from the
  token. The recipe library stays shared; plans, pantry, targets, favourites and
  notes become per-household. Basic auth stays behind a setting for one release.
- **Capture automation.** An iOS Shortcut that posts a shared link to the queue,
  so capture needs no laptop. Retire the local scripts once the queue is in daily
  use (keep `export` and `db dump`).

## Deferred

- pgvector (semantic search uses JSON embeddings plus Python cosine until ~10k rows).
- A native shell (Capacitor around the same web code) until a share-sheet or
  notification need is real. React Native is off the board.
- Screenshot or OCR capture. Capture is link plus pasted caption only.

## Key decisions

- **Neon is the source of truth for everything the user writes** (plans, pantry,
  targets, favourites, notes, manual recipes). Local Postgres is the ingest and
  extraction workshop. `sync push` moves Instagram recipe improvements to Neon: it
  inserts new recipes and updates only fields Neon has not edited, never deleting.
- **Extraction may run from the app against Neon** (the queue flow). This reverses
  the older "extraction never runs against Neon" rule, which assumed extraction ran
  only locally with batch state on disk. The queue submits a batch, an import step
  applies and promotes. The recipe is born on import, not on launch.
- **Editing widens the existing PATCH and `edited_fields`.** No second override
  table, no per-field history beyond what `extractions` already keeps. Revert drops
  the field from `edited_fields` and re-applies the latest extraction.
- **Promotion never overwrites a user-edited field.** `promote()` merges an
  extraction into a recipe, preserving identity, media, caption and `edited_fields`.
- **Balance targets follow the Mediterranean pyramid.** Plant categories are floors
  with no "Over"; animal categories keep a ceiling and lose any floor.
- **Migrations replace DDL at startup.** Alembic is the source of truth for schema;
  `init_db` upgrades to head and adopts existing databases by stamping the baseline.
- **MCP accepts only allow-listed token subjects**, until the `users` table exists.

## Domain facts worth keeping in mind

- Recipes are keyed by the Instagram shortcode (`code`), never `Media.id`. All
  Instagram ids are stored as strings (they overflow JS number precision).
- Title, ingredients and instructions stay verbatim in the caption's language
  (mostly Italian). Tag and classification fields use canonical English; a synonym
  layer bridges the two for search.
- Two hashes drive change detection: `caption_hash` ("re-extract?") and the
  embedding source hash ("re-embed?"). They move for different reasons; keep them
  separate.
- Instagram media URLs expire, so the durable Cloudinary URL is captured at
  ingestion time and is the source of truth for the image.

## Known follow-ups

- The synonym layer is a hand-maintained cross-language workaround. The real fix is
  a canonical ingredient identity (a stable id per ingredient, rendered in the
  chosen language) rather than string aliasing. Revisit when i18n is tackled.
- Several large files (`cli.py`, `recipes_db.py`, the recipes router) are past the
  ~200-line smell. Split by responsibility in the commit before the next feature
  that touches them, not as standalone churn.
- Re-run the restore drill after each schema change: restore the latest Neon dump
  into a throwaway Postgres container and check the row counts.
