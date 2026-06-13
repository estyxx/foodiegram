# Foodiegram — Revival Plan

A staged roadmap from the current (working but messy) state to a clean,
searchable, editable, meal-planning recipe app. Built so each phase ships
something usable on its own.

---

## 1. Where the code actually is

The pipeline *works* — you've extracted real recipes (the lemon-chicken escalopes
came through with full ingredients, English translation, and ~30 tag fields). The
problems are consistency and sprawl, not capability:

- **Name drift.** Resolved: the one name is `foodiegram`. The Python package and
  all imports already use it; remaining `cookstagram` references live only in docs,
  the frontend, and live infra (the `cookstagram-data` repo / Vercel URL).
- **Two `Recipe` models.** `types.py` defines an old, thin `Recipe`
  (`post_id`, `dish_type` enum…) but your real data and `recipe_extractor.py` use a
  much richer one (`proteins`, `vegetables`, `cooking_methods`, `season`,
  `occasion`, `style_tags`…). `types.py` also imports `Collection`/`ExtractedRecipe`
  it never defines — it's stale. One model, one file.
- **Two analyzers.** `analyzer.py` (old: two `chat.completions` calls per post,
  expensive, has a dead `__post_init__` that never runs on a Pydantic model) and
  `recipe_extractor.py` (new: Batch API, JSON schema). Keep the batch one, delete
  the old one.
- **Corrupted IDs.** Recipes were keyed off `Media.id` (= `"{pk}_{userid}"`),
  producing keys like `36329647417694707168004905221`. The real post is
  `pk=3632964741769470716`, `code=DJq4i8ysCL8`. Fix: key by **`code`**, store all
  IDs as **strings**.
- **`repository.py` references fields the model doesn't have** (`post_pk`,
  `cooking_methods` on the wrong model) — it was written against a different Recipe
  shape. It'll only line up once there's one model.
- **Frontend sprawl.** `index.html`, `mobile.html`, `foodiegram.html`,
  `recipe.html`, `analytics.html`, `planner.html` + `app.js` + `recipe.js` are
  overlapping single-file apps. Collapse to one.
- **Error handling** is `print` + bare `except` + `traceback.print_exc()`
  throughout — the opposite of the clean conventions you want.

None of this is hard to fix. It's mostly consolidation.

---

## 2. Target architecture (DDD-lite, no over-engineering)

```
src/foodiegram/
  domain/        models.py, enums.py, errors.py   ← pure, no I/O
  instagram/     client.py, cache.py              ← instagrapi adapter
  ai/            extractor.py, prompts/*.txt       ← batch + interactive extraction
  images/        cloudinary.py                     ← download → upload → durable URL
  storage/       repository.py                      ← JSON now, SQLite later (same API)
  app/           pipeline.py                        ← orchestration (use-cases)
  settings.py                                       ← pydantic-settings
  cli.py                                            ← typer: fetch / analyze / build
  api.py                                            ← FastAPI (Phase 3+)
frontend/        one app (search + filters + detail + planner)
data/            private — separate private repo, git-ignored here
```

Dependency direction is inward only: `cli/api → app → adapters → domain`. The
domain layer imports nothing from the others. That single rule buys you most of
what "clean architecture" is actually for, with none of the ceremony. No
unit-of-work, no domain events, no generic base service — add an abstraction only
when you have a second real implementation.

---

## 3. Key decisions

| Question | Decision | Why |
|---|---|---|
| Storage (now) | JSON files, keyed by `code` | Already there; zero infra; fine to read statically |
| Storage (when you edit) | **SQLite** behind the same repository interface | File-based, free, FTS5 search, no server. Migrate when writes appear |
| Search | Client-side over caption + tags (MVP) → SQLite **FTS5** later | Bilingual works if you index original caption *and* normalized tags |
| Hosting (frontend) | Static host (Vercel / Cloudflare Pages / GH Pages) | Free; the MVP is just static files + one JSON |
| Hosting (backend) | Your FastAPI Cloud access (or Fly/Railway) — Phase 3 only | Don't stand up a server until editing/planning needs one |
| Images | Cloudinary free tier: capture at extract time, store URL + `public_id` | IG URLs expire; this is the real reason to fetch media early |
| Bilingual | Preserve original caption + `ingredients_original`; add normalized EN tags | Search either language; never overwrite the Italian |
| Manual fixes (pre-DB) | `overrides/{code}.json` merged at build time | Hand-correct the LLM without standing up a database yet |

---

## 4. One data model (the direction)

Collapse to a single `Recipe` Pydantic model, frozen, keyed by `code`:

- **Identity:** `code: str`, `pk: str`, `post_url` (derived), `caption` (verbatim).
- **Core:** `title`, `ingredients: list[str]`, `ingredients_original: list[str]`,
  `instructions: list[str]`.
- **Classifications (enums):** `meal_type`, `dish_type`, `cuisine_type`,
  `difficulty`.
- **Open tag lists:** `proteins`, `vegetables`, `grains_starches`, `herbs_spices`,
  `cooking_methods`, `dietary_tags`, `health_tags`, `style_tags`, `season`,
  `occasion`. (Keep these as `list[str]` — don't enum them; they grow.)
- **Times/serving:** `prep_time`, `cook_time`, `total_time`, `servings`.
- **Media:** `image_url` (Cloudinary), `image_public_id`, `thumbnail_url`.
- **Provenance:** `is_recipe: bool`, `confidence: float`, `extracted_at`,
  `model_used`, `edited_by_user: bool`.

Plus a small `MealPlan` model for Phase 4 (week → list of `code`s per day) and a
`GroceryList` derived from selected recipes' ingredients.

---

## 5. Phased roadmap

Each phase is shippable. Do them in order; don't skip to Phase 3.

### Phase 0 — Cleanup & foundation
*Goal: one clean skeleton that still runs.*
- Pick the name; rename package, scripts, README to match.
- Create the `domain/` layer; consolidate to **one** `Recipe` model + enums + errors.
- Delete `analyzer.py` and the duplicate HTML files; keep the best one frontend.
- Switch to `pydantic-settings`; move `logging.basicConfig` to the entrypoint only.
- Fix IDs: key by `code`, all IDs `str`. Write the JSON→new-model migration once.
- Get `ruff`, `mypy --strict`, `pytest` green on the skeleton.

### Phase 1 — MVP pipeline (extract → analyze → static site)
*Goal: re-run end to end and browse the result.*
- `foodiegram fetch <collection>` → instagrapi → cache JSON (keyed by `code`).
- Image step: download media → Cloudinary → store durable URL + `public_id`.
- `foodiegram analyze` → **Batch API** → validated `Recipe` JSON per post.
- `foodiegram build` → emit one `recipes.json` (+ a small `index.json`) the
  frontend reads.
- One clean frontend: card grid, text search, multi-filter (cuisine, meal, dietary,
  protein). Data in the **private** repo; code stays public.

### Phase 2 — Quality & bilingual
*Goal: trust the data, search in both languages, fix mistakes without a DB.*
- Flag low-confidence / `is_recipe=false` for review; re-run those interactively
  with Pydantic AI.
- Handle photo-only posts (no caption recipe) — mark them, or add vision later.
- Bilingual search over caption + `ingredients_original` + normalized tags.
- `overrides/{code}.json` merged at build → you hand-edit; re-running extract never
  clobbers your edits.

### Phase 3 — Editing + database
*Goal: edit in the UI; this is when a backend earns its place.*
- FastAPI + **SQLite (FTS5)**. Migrate JSON → SQLite (same repository interface, so
  the swap is contained).
- CRUD endpoints for recipes; edit UI in the frontend. `edited_by_user` protects
  your changes from re-extraction.

### Phase 4 — Meal planning
*Goal: the thing you actually want this for.*
- `MealPlan`: pick recipes into a weekly board; a "to-cook" mood board.
- Auto-generate a grocery list by aggregating ingredients across selected recipes
  (dedupe + group by category — your `vegetables`/`proteins`/etc. tags make this easy).
- Optional later: PWA/offline, cooking-mode timers.

---

## 6. Suggested first sitting (ADHD-friendly, ~one focused block)

1. Rename to one project name.
2. Create `domain/models.py` with the single `Recipe` model + enums.
3. Write a 20-line script: load existing `extracted_recipes.json`, re-key by `code`,
   validate through the new model, write to `data/recipes/{code}.json`.
4. Run it. You now have clean, correctly-keyed data and a model everything else can
   build on. Everything in Phase 1 hangs off that.

Drop `CLAUDE.md` in the repo root before you start so Cursor codes to these rules
from the first prompt.
