# DISPENSA 🫙 — Master Plan (final, Cursor-ready)

*This is the single canonical document. It supersedes plan v1/v2/v3 and `plan.md`.
Repo: `estyxx/foodiegram` (package rename → `dispensa` deferred to Phase 5).
All decisions below are LOCKED unless marked open. Work phase by phase, one task at a time.
Definition of done, always: `ruff check --fix . && ruff format . && mypy . && pytest` green
(+ `tsc --noEmit` once the frontend exists). CLAUDE.md conventions apply to every line.*

---

# PART I — WHAT WE ARE BUILDING

## 1. Product brief

**Dispensa** is a personal recipe library and Mediterranean-diet weekly meal planner.
~800 recipes extracted from saved Instagram posts (mostly Italian; titles/ingredients/
instructions stay verbatim in the original language, classifications in English) plus,
eventually, manually added recipes. The signature feature: a **live, colour-coded weekly
balance panel** tracking 7 protein categories against Mediterranean targets — adding or
removing a recipe from the week moves the bars in real time and suggests gap-fillers.
Pantry-lite awareness ("7/9 in kitchen", shopping list). ADHD-friendly, warm, editorial,
accessible. Solo hobby project: simple, readable, robust. A future AI layer (Phase 7)
learns tastes and reduces waste — deliberately last.

## 2. The Mediterranean engine (product core)

7 tracked categories, one fixed colour each, used identically everywhere (balance panel,
day chips, recipe badges, plan chips). Cooler = eat more, warmer = go easy. **Colour is
never the only signal** — always paired with a text label or icon.

| Category | Weekly target (default, user-editable) | Rule copy |
|---|---|---|
| fish | 2–3 | "at least twice a week; aim for ≥1 oily" |
| legumes | 2–3 | "≥2–3 a week" |
| poultry | 1–2 | "moderate" |
| eggs | 2–4 | "2–4 a week" |
| dairy | 0–7 (soft) | "small portions; limit hard cheese" |
| red_meat | 0–2 | "occasional, lean cuts" |
| processed_meat | 0–1 | "rarely" |

Rules:
- A recipe can count toward **multiple categories** (carbonara = eggs + processed_meat + dairy).
- **Cured meats are processed meat by guideline definition** (guanciale, pancetta, salsiccia,
  salame, prosciutto, speck, mortadella, 'nduja, wurstel). When they are the backbone of the
  dish (carbonara, amatriciana, gricia) they count at full weight; garnish-level uses follow
  the substantiality threshold below.
- Count a category only when **substantial** (~≥30 g per portion or central to the dish).
  Grated parmigiano to finish: no dairy. Cacio e pepe / parmigiana: dairy.
- **Daily base** (veg, fruit, whole grains, EVOO, nuts, herbs) is shown as gentle reminders,
  never counted in the panel.
- **Plant-based leaf badge** is derived from `dietary_tags` (vegetarian/vegan), rendered in a
  colour that is NOT the legumes green, shown on cards/Browse, never in the balance panel.
- **Balance counts slots, not portions.** Cook fish once, eat it twice (leftovers) = plan it
  on two days = 2 fish servings. The `portions` field exists only for scaling and shopping.

---

# PART II — DECISIONS (all locked)

| # | Decision |
|---|---|
| D1 | Deploy on **FastAPI Cloud**: one `fastapi deploy` ships API + frontend (StaticFiles). Filesystem is ephemeral — nothing mutable on disk in prod. |
| D2 | **Database is the single source of truth for recipes.** Deploy artifact = code only. Data reaches prod via local scripts pointed at Neon (`DATABASE_URL`). |
| D3 | **Two-entity model**: `extractions` (append-only, immutable LLM outputs with prompt/model provenance) vs `recipes` (mutable canonical state). `promote()` is the only path between them and never overwrites user-edited fields. |
| D4 | **ORM: `sqlmodel`** (approved). SQLite locally, Neon Postgres in prod, one codebase. `SQLModel.metadata.create_all` for now; alembic only when schema churn demands it. SQLModel rows NEVER leave `storage/` — repositories return domain models. |
| D5 | **pydantic-ai** gets three jobs: single-recipe repair, category review loop, paste-any-text → structured recipe. OpenAI Batch API remains the bulk path. |
| D6 | Full re-extraction with **prompt v2**: adds `mediterranean_categories`, `course` (approved), extends `dish_type`. Carbonara counts processed_meat at full weight (guideline-honest). |
| D7 | **Frontend: no-build vanilla ES modules**, pure function components, tiny pub-sub store, JSDoc + `// @ts-check`, `tsc --noEmit` in `make check`. `typescript` is the only devDependency. |
| D8 | **Pantry-lite**: name + staple/fresh + optional expiry. No quantities, no depletion, ever (until real usage proves otherwise). |
| D9 | **DDD-lite**: `api/scripts → app → storage\|ai\|instagram\|images → domain`. Domain is pure (no I/O, SDKs, env, clock). Enforced by `tests/test_architecture.py`. |
| D10 | JSON files demote to **pipeline artifact + export/backup**: `scripts/export.py` dumps DB → `data/recipes/*.json` (sorted keys) → committed to a private data repo → backup + free `git diff` of the data. |
| D11 | **Identity**: `code: str` stays PK. Instagram = shortcode; manual = `m-{slugified-title}-{4 random base32}`. New `source: RecipeSource`; `pk`/`post_url`/`caption` become `\| None`. |
| D12 | **Search stays client-side** over a slim `GET /api/recipes` index cached per session (~800 recipes). No FTS. |
| D13 | **Auth: HTTP Basic middleware over EVERYTHING** (static + API). `BASIC_AUTH_USERNAME`/`BASIC_AUTH_PASSWORD` env vars; auth disabled when unset (local dev). `secrets.compare_digest`. Zero login UI. |
| D14 | **Thumbnails at ingest**: Cloudinary server-side fetch of the CDN URLs in the IGbulkCollector export immediately at ingest, while URLs are fresh. New recipes never depend on instagrapi recovering. |
| D15 | **`is_recipe=false` posts are normal `recipes` rows**, surfaced only in a collapsed "Appunti & ispirazione" shelf in Browse, excluded from planner suggestions. |
| D16 | **Deferred, door open**: recipe variants (`parent_code: str \| None` someday), vision on photo-only posts, repo/package rename (Phase 5), Browse "Goals & Profile" screen, backup automation (manual export is fine solo), AI layer design (Phase 7 only after ≥3–4 weeks of real use). |

---

# PART III — ARCHITECTURE

## 3. Package layout (target; Phase 0 creates it by pure moves)

```
src/foodiegram/
├── domain/                      # PURE — no I/O, no SDKs, no env, no clock
│   ├── enums.py                 # + MedCategory, Course, RecipeSource; DishType extended
│   ├── errors.py
│   ├── models.py                # Recipe, ExtractedRecipe, Extraction, CategoryServing
│   ├── editing.py               # promote(), user-owned-field rules
│   ├── diffing.py               # field-level diff between extraction payloads
│   ├── planning.py              # WeekPlan, PlannedMeal, targets, balance math
│   ├── pantry.py                # PantryItem, kitchen_match
│   ├── shopping.py              # shopping-list aggregation
│   └── synonyms.py              # (existing)
├── app/                         # use-cases — orchestration, no HTTP types
│   ├── ingest.py                # food.json → posts staging + recipe stubs + thumbnails
│   ├── extraction.py            # submit/apply batch → extraction rows
│   ├── promotion.py             # batch/extraction → recipes via domain promote()
│   ├── edit_recipe.py           # apply user edits, maintain edited_fields
│   ├── add_recipe.py            # manual create + paste-text flow
│   ├── plan_week.py             # plan CRUD + balance + suggestions
│   ├── shopping_list.py
│   ├── user_state.py            # favourites / notes
│   └── export.py                # DB → JSON files
├── storage/
│   ├── db.py                    # SQLModel engine/session; pool_pre_ping=True
│   ├── recipes_db.py            # RecipeRepository (DB-backed)
│   ├── extractions_db.py        # append-only ExtractionRepository
│   ├── plans_db.py  pantry_db.py  user_state_db.py  targets_db.py
│   └── recipes_json.py          # legacy JSON read/write — import/export ONLY
├── ai/
│   ├── batch.py                 # OpenAI Batch submit/status/apply; PROMPT_VERSION = "2"
│   ├── repair.py                # pydantic-ai agents (full re-extract, categories-only,
│   │                            #   free-text → ExtractedRecipe)
│   └── prompts/extract_recipe_details.txt
├── instagram/                   # _auth.py, extractor, cache_manager (existing, moved)
├── images/                      # cloudinary helpers (existing, moved)
├── api.py + routers/            # recipes, plans, pantry, shopping, targets
├── api_models.py
└── settings.py                  # + database_url, basic_auth_*, default targets

frontend/                        # renamed from public/, structured (Part VI)
scripts/                         # thin argparse wrappers over app/ (Part V)
tests/                           # domain/ = full coverage; storage = sqlite-tmp round-trips
```

**Dependency rule (CI-enforced):** nothing in `domain/` imports from any sibling package.
`tests/test_architecture.py` walks `ast.parse` imports of every module under `domain/` and
fails on `foodiegram.(storage|ai|instagram|images|app|api)`.

## 4. The recipe data lifecycle

```
LOCAL (manual, ~monthly)                                          DB (SQLite dev / Neon prod)
Instagram app (browse & save — keeps the account warm)
  ↓ IGbulkCollector (browser ext) → export post list
  ↓ IGbulkDL --dry-run → food.json (captions + CDN urls)
  ↓ scripts/ingest.py food.json      ─ posts staged, stubs created,
                                       thumbnails → Cloudinary NOW (D14) ──► posts, recipes(stubs)
  ↓ scripts/extract.py submit / status / apply (Batch, prompt vN) ────────► extractions (append-only)
  ↓ scripts/diff_batch.py --from-version N-1 --to-version N   "what changed?"
  ↓ scripts/promote.py --version N [--dry-run]  — respects edited_fields ─► recipes (canonical)
  ↓ scripts/review_categories.py (pydantic-ai, interactive fixes)
  ↓ scripts/export.py → data/recipes/*.json → commit in PRIVATE DATA REPO (backup + git diff)

Web app (prod): read recipes · plan weeks · edit recipes (Phase 6) · add manual recipes (Phase 6)
```

Invariants:
1. `extractions` is **append-only** — no row is ever updated or deleted.
2. The app reads **only** `recipes`.
3. `promote()` is the **only** extraction→recipe path and skips `edited_fields`.
4. Ingestion is local **by design** — the Instagram-flaky part never runs on a server.

---

# PART IV — DOMAIN & DATA SPECS

## 5. Enums (`domain/enums.py`)

```python
class MedCategory(StrEnum):
    """Mediterranean-diet tracked category (the 7-colour key)."""
    FISH = "fish"; LEGUMES = "legumes"; POULTRY = "poultry"; EGGS = "eggs"
    DAIRY = "dairy"; RED_MEAT = "red_meat"; PROCESSED_MEAT = "processed_meat"

class Course(StrEnum):
    """Italian meal-structure grouping — Browse shelf order."""
    ANTIPASTO = "antipasto"; PRIMO = "primo"; SECONDO = "secondo"
    CONTORNO = "contorno"; DOLCE = "dolce"; LIEVITATI = "lievitati"
    COLAZIONE = "colazione"; OTHER = "other"; UNKNOWN = "unknown"

class RecipeSource(StrEnum):
    INSTAGRAM = "instagram"; MANUAL = "manual"
```

Extend `DishType` with: `PASTA = "pasta"`, `RISOTTO = "risotto"`, `PIZZA = "pizza"`,
`SANDWICH = "sandwich"`, `PASTRY = "pastry"`. Keep all existing values.

## 6. Models (`domain/models.py`)

```python
class CategoryServing(BaseModel):
    """How much a recipe counts toward one Mediterranean category."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    category: MedCategory
    servings: float = 1.0            # 1.0 main component; 0.5 substantial-but-secondary
    is_oily_fish: bool = False       # meaningful only when category == FISH
    source: Literal["llm", "derived", "manual"] = "llm"
```

`Recipe` — changes to the existing model:
- `code: str` PK (shortcode or `m-…`), new `source: RecipeSource = RecipeSource.INSTAGRAM`
- `pk: str | None`, `post_url: str | None`, `caption: str | None`
- `mediterranean_categories: list[CategoryServing] = Field(default_factory=list)`
- `course: Course = Course.UNKNOWN`
- `prompt_version: str | None = None`
- `edited_fields: frozenset[str] = frozenset()`  ← replaces `edited_by_user` (keep the bool
  through migration, drop after)
- `archived: bool = False` (soft-hide for IG recipes; see §13)
- REMOVE `is_favorite` / `user_notes` → they live in `user_state` (migration script §11)

`ExtractedRecipe` — add `mediterranean_categories: list[ExtractedCategoryServing]`
(sub-model: `category: str, servings: float, is_oily_fish: bool`) and `course: str`.
`Recipe.from_extracted` maps them with the same try/ValueError→UNKNOWN pattern as the
other enums, dropping unknown category strings with a logged warning at the caller edge.

```python
class Extraction(BaseModel):
    """One immutable LLM extraction run for one post. Append-only."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: int | None
    recipe_code: str
    prompt_version: str
    model: str
    batch_id: str | None             # None for pydantic-ai one-offs
    kind: Literal["batch", "repair", "categories", "paste"]
    extracted_at: datetime
    payload: ExtractedRecipe
```

## 7. Editing & diffing (`domain/editing.py`, `domain/diffing.py`) — pure, exhaustively tested

```python
PROTECTED_FIELDS: frozenset[str]     # never touched by promote():
# {"code", "source", "pk", "post_url", "caption", "cloudinary_url",
#  "thumbnail_url", "edited_fields", "archived"}

def promote(current: Recipe, extraction: Extraction) -> Recipe:
    """Apply an extraction to a recipe, preserving user-edited fields."""
    # For every field produced by Recipe.from_extracted: take extraction value
    # UNLESS name ∈ current.edited_fields ∪ PROTECTED_FIELDS.
    # Stamp prompt_version / model_used / extracted_at from the extraction.

class FieldDiff(BaseModel):          # frozen
    field: str
    old: object
    new: object

def diff_payloads(a: ExtractedRecipe, b: ExtractedRecipe) -> list[FieldDiff]: ...
    # Order-insensitive for tag lists; order-SENSITIVE for ingredients/instructions.

def diff_against_recipe(recipe: Recipe, extraction: Extraction) -> list[FieldDiff]: ...
    # What WOULD change if promoted (excluding edited/protected) — the dry-run view.
```

**The single most important test in the codebase:** promote() with
`edited_fields={"ingredients"}` must keep the user's ingredients while updating
everything else, idempotently.

## 8. Planning (`domain/planning.py`) — pure

```python
class PlannedMeal(BaseModel):        # frozen
    day: date
    meal: Literal["lunch", "dinner"]
    recipe_code: str
    portions: int = 2                # scaling/shopping ONLY — never balance

class WeekPlan(BaseModel):           # frozen
    week_start: date                 # validator: must be a Monday
    meals: tuple[PlannedMeal, ...] = ()

class CategoryTarget(BaseModel):     # frozen
    category: MedCategory
    min_servings: float
    max_servings: float

DEFAULT_TARGETS: tuple[CategoryTarget, ...]   # values from §2 table

class CategoryStatus(BaseModel):     # frozen
    category: MedCategory
    planned: float
    target: CategoryTarget
    state: Literal["under", "ok", "over"]     # >max ⇒ over; ≥min ⇒ ok; else under

def week_balance(plan: WeekPlan, recipes: Mapping[str, Recipe],
                 targets: Sequence[CategoryTarget]) -> list[CategoryStatus]:
    # Sum CategoryServing.servings per category across meals (each SLOT counts once).
    # Multi-category recipes contribute to each. Unknown codes: skip (caller logs).

def oily_fish_count(plan: WeekPlan, recipes: Mapping[str, Recipe]) -> float: ...

def gap_suggestions(statuses: Sequence[CategoryStatus], candidates: Sequence[Recipe],
                    *, limit_per_category: int = 3) -> dict[MedCategory, list[Recipe]]:
    # For each "under" category: candidates counting toward it, is_recipe=True,
    # not archived, not already planned; ranked by confidence desc, then favourites
    # (favourite codes passed in by the app layer — domain stays pure).
```

## 9. Pantry & shopping (`domain/pantry.py`, `domain/shopping.py`) — pure

```python
class PantryItem(BaseModel):         # frozen
    name: str                        # lowercase-normalised for matching
    kind: Literal["staple", "fresh"]
    expires: date | None = None      # fresh only, optional

class KitchenMatch(BaseModel):       # frozen
    have: list[str]                  # raw ingredient lines matched
    missing: list[str]

def kitchen_match(ingredients: Sequence[str], pantry: Sequence[PantryItem],
                  synonyms: SynonymIndex) -> KitchenMatch:
    # Match = any pantry name (synonym-expanded, both languages) appears as a
    # word-boundary substring of the raw ingredient line. Deliberately naive.

class AisleGroup(BaseModel):         # frozen
    aisle: str
    items: list[ShoppingItem]        # canonical name + the raw source lines

def shopping_list(plan, recipes, pantry, synonyms,
                  aisles: Mapping[str, str]) -> list[AisleGroup]:
    # Collect `missing` across the week's meals, strip quantities (reuse scale regex),
    # lowercase, synonym-canonicalise, de-duplicate keeping raw lines as detail,
    # group via data/aisles.json; unknown → "altro".
```

## 10. Database schema (SQLModel; SQLite dev / Neon prod)

```
recipes(code TEXT PK, source TEXT, ...all Recipe fields..., edited_fields JSON,
        archived BOOL, created_at, updated_at)
extractions(id PK, recipe_code FK→recipes ON DELETE CASCADE, prompt_version TEXT,
        model TEXT, batch_id TEXT NULL, kind TEXT, extracted_at TIMESTAMP,
        payload JSON)                                  -- APPEND-ONLY
posts(code TEXT PK, caption TEXT, taken_at TIMESTAMP NULL,
        collection_names JSON, ingested_at TIMESTAMP)  -- staging
week_plans(id PK, week_start DATE UNIQUE)
planned_meals(id PK, plan_id FK, day DATE, meal TEXT, recipe_code TEXT, portions INT)
pantry_items(id PK, name TEXT, kind TEXT, expires DATE NULL)
user_state(recipe_code TEXT PK, is_favorite BOOL, user_notes TEXT NULL, updated_at)
targets(category TEXT PK, min_servings REAL, max_servings REAL)  -- seeded from
                                                                 -- DEFAULT_TARGETS if empty
```

JSON columns via `sa_column=Column(JSON)` (TEXT-JSON on SQLite, jsonb on Postgres).
Repositories convert row ⇄ domain model at their boundary; SQLModel classes are private
to `storage/`. Engine: `create_engine(settings.database_url, pool_pre_ping=True)`;
Neon: use the **pooled** connection string.

## 11. API (routers; all behind Basic auth middleware, D13)

```
GET    /api/recipes                       → slim index (code, title, course, dish/meal type,
                                            categories, dietary_tags, times, thumb, kitchen X/Y
                                            once pantry exists) — the client-side search corpus
GET    /api/recipes/{code}                → full RecipeDetail
PATCH  /api/recipes/{code}                → partial update; app layer adds every present field
                                            to edited_fields; writes user_state for
                                            is_favorite/user_notes keys
POST   /api/recipes                       → manual create (Phase 6)
POST   /api/recipes/extract-text          → paste text → ExtractedRecipe preview (Phase 6)
DELETE /api/recipes/{code}                → manual: delete; instagram: archived=True (Phase 6)
GET    /api/plans/{week_start}            → plan + balance + suggestions (ONE payload; FE does
                                            no balance math)
PUT    /api/plans/{week_start}/meals      → upsert a meal slot (idempotent)
DELETE /api/plans/{week_start}/meals/{id}
GET    /api/plans/{week_start}/shopping-list
GET/POST/DELETE /api/pantry[/{id}]
GET/PUT /api/targets
```

Auth middleware: if `settings.basic_auth_username` set → require Basic on every request
(static included), `secrets.compare_digest`, else no-op (dev). `401` with
`WWW-Authenticate: Basic realm="dispensa"`.

**Migration (one-shot):** `scripts/migrate_user_state.py` — move existing
`is_favorite`/`user_notes` out of recipe JSON into `user_state` on import.

---

# PART V — TOOLING & RUNBOOK

## 12. Scripts (thin argparse wrappers over `app/`; all honour `DATABASE_URL`, unset → `sqlite:///data/dispensa.db`; every destructive script has `--dry-run`)

| Script | Behaviour |
|---|---|
| `ingest.py <food.json>` | Parse IGbulkDL export → upsert `posts` → create recipe stubs for unknown codes (`source=instagram`) → **immediately** Cloudinary-fetch each fresh CDN thumbnail URL (D14). Prints `N new, M known, T thumbnails uploaded`. |
| `extract.py submit [--all\|--only-missing]` | Build `batch_input.jsonl` from staged captions (`--only-missing` = no extraction at current `PROMPT_VERSION`), submit to OpenAI Batch. |
| `extract.py status` / `extract.py apply` | Poll; `apply` validates each result into `ExtractedRecipe` and writes **`extractions` rows only** (kind=`batch`). Never touches `recipes`. Keep `batch_output.jsonl` files — they backfill history. |
| `diff_batch.py --from-version 1 --to-version 2 [--summary] [--field F] [--code X]` | Per-recipe `diff_payloads` between the latest extraction at each version. `--summary` prints aggregates ("312 recipes changed ≥1 field; dish_type: 74, mostly main_course→pasta; categories added on 590"). **This answers "I changed the prompt/model — what actually changed?"** |
| `promote.py --version 2 [--batch id] [--dry-run]` | Per recipe: `diff_against_recipe` → print (dry-run) or `promote()` + save. Summary includes `K fields skipped (user-edited)`. |
| `review_categories.py` | List recipes where confidence <0.6 OR categories empty but proteins non-empty OR a processed-meat keyword appears without the category. Per recipe: pydantic-ai categories-only agent → show → y/n → accepted writes an edit (`edited_fields += {"mediterranean_categories"}`, `source="manual"`). |
| `repair_recipe.py <code>` | pydantic-ai full re-extraction of one caption → extraction row (kind=`repair`) → diff → y/n promote. |
| `export.py [--out data/recipes]` | DB → one JSON per recipe, canonical `Recipe` shape, **sorted keys** (stable git diffs). Run after each batch/edit session; commit in the private data repo. |
| `import_json.py <dir>` | Inverse of export. Used for the initial prod load and disaster recovery. Runs `migrate_user_state` logic for legacy files. |

## 13. Runbook (goes verbatim in README, replacing the stale Cookstagram copy)

**Syncing new saved posts (~monthly, local):**
1. Browse/save on the phone as normal (keeps the account warm).
2. Run IGbulkCollector in the browser → export the post list.
3. `IGbulkDL --dry-run` → `food.json` (captions + CDN URLs; no media downloads).
4. `uv run scripts/ingest.py food.json` (thumbnails upload NOW — URLs expire).
5. `uv run scripts/extract.py submit --only-missing` → wait → `status` → `apply`.
6. `uv run scripts/promote.py --version 2 --dry-run` → review → run without `--dry-run`.
7. `uv run scripts/export.py` → commit + push in the private data repo.

**Against prod:** prefix any of the above with `DATABASE_URL=<neon-pooled-url>`.

**Changing the prompt or model:**
bump `PROMPT_VERSION` in `ai/batch.py` → `extract.py submit --all` → `apply` →
`diff_batch.py --from-version N-1 --to-version N --summary` → inspect → `promote.py
--version N --dry-run` → promote → `export.py` + commit. User edits are never at risk.

**Instagram account note:** instagrapi login is currently flagged; nothing in this plan
depends on it. If it recovers, `fetch_missing_posts.py` becomes a convenience again.
Never run Instagram-facing code on the server.

---

# PART VI — FRONTEND

## 14. Structure (rename `public/` → `frontend/`; split the 1269-line index.html)

```
frontend/
├── index.html                 # shell: <header>, <nav>, <main id="view">, skip-link
├── jsconfig.json              # checkJs, strict, noEmit target for tsc
├── css/
│   ├── tokens.css             # design tokens ONLY (§16)
│   ├── base.css               # reset, typography, focus rings, prefers-reduced-motion
│   └── components.css         # one section per component (.balance-panel__bar …)
└── js/
    ├── main.js                # hash router: #week, #plan, #recipe/{code}, #browse
    ├── api/client.js          # fetch wrapper + JSDoc @typedefs for every DTO
    ├── state/store.js         # ~40 lines: createStore(initial) → {get,set,subscribe}
    ├── lib/scale.js           # extractNumber/scaleIngredient (moved from inline)
    ├── lib/format.js          # it-IT dates, quantities
    ├── components/
    │   ├── BalancePanel.js    # THE component — bars per category, label+colour+state,
    │   │                      #   aria-live="polite" announcing changes
    │   ├── CategoryChip.js    # colour + text label (never colour alone)
    │   ├── RecipeCard.js      # serif title, mono meta, chips, kitchen X/Y, save star
    │   ├── DayColumn.js       # slots; "add to day" menu = keyboard drag-drop alternative
    │   ├── GapSuggestions.js
    │   ├── IngredientRow.js   # mono qty + body-font name + have/need flag
    │   ├── ServingsStepper.js # + ingredient-anchored rescale mode
    │   └── PantryList.js
    └── views/ week.js  plan.js  detail.js  browse.js  (+ edit.js in Phase 6)
```

## 15. JS conventions (append to CLAUDE.md as the JS mirror of the Python rules)

1. Every file starts `// @ts-check`; DTO `@typedef`s live in `api/client.js`;
   `tsc --noEmit -p frontend/jsconfig.json` is part of `make check`. Red types ≠ done.
2. Components are **pure functions `(props) => HTMLElement`** using
   `document.createElement` / `<template>` clones. **Never `innerHTML` with dynamic
   values** (recipes contain arbitrary Instagram text) — `textContent` only.
3. State flows down as props; changes flow up via `store.set()`; views re-render their
   region on `store.subscribe`. No component touches another component's DOM.
4. No classes unless the platform demands it; no globals outside `main.js` bootstrap;
   ES modules; `const` by default.
5. Naming: components `PascalCase.js`, everything else `camelCase`; handlers named for
   intent (`onAddMeal`, not `handleClick2`).
6. **Accessibility is a review gate**: real `<label>`/`aria-label` on every control;
   drag-drop always has the menu path; balance changes announced via live region;
   visible focus; ≥44px targets; `prefers-reduced-motion` respected.
7. No frameworks, no npm runtime deps, no build step. `typescript` (checker) is the
   single devDependency.

## 16. Design tokens (`css/tokens.css`) — first FE task

Open `Dispensa v3.dc.html`, lift the **exact** values, verify every text/ground pair for
WCAG AA (darken until it passes):

```css
:root {
  --font-display: …;  --font-mono: …;  --font-body: …;   /* three type jobs */
  --paper: …;  --ink: …;
  --cat-fish: …; --cat-legumes: …; --cat-poultry: …; --cat-eggs: …;
  --cat-dairy: …; --cat-red-meat: …; --cat-processed: …; /* outlined red-meat variant ok */
  --badge-plant: …;    /* MUST NOT equal --cat-legumes */
  --focus-ring: …;     /* high contrast */
}
```

## 17. View acceptance criteria

- **#week (Home):** balance panel above the fold; Mon–Sun strip of DayColumn chips;
  "Cook tonight" = today's dinner; "From your kitchen" = top 3 by kitchen-match ratio,
  expiring items flagged; "Plan the week" CTA → #plan.
- **#plan:** 7 columns (rows <768px) + sticky right rail (balance, gap suggestions,
  shopping-list button). Adding a recipe optimistically updates the store → panel
  animates (skipped under reduced-motion) → PUT; rollback on failure.
- **#recipe/{code}:** magazine layout per Dispensa v3; "Counts as: 🐟 Fish · oily" line;
  both scaling modes share `lib/scale.js`; actions: save, add-to-day menu,
  add-missing-to-list; "✎ edited" mono marker on user-owned fields (Phase 6).
- **#browse:** search + chip filters (category colours, meal, time, dietary, course);
  shelves grouped by `course` in Italian order (antipasti → primi → secondi → contorni →
  lievitati → dolci); `is_recipe=false` only in a collapsed "Appunti & ispirazione"
  shelf; collection presets (Pasta, Soups, Pumpkin…) as one-tap saved filter combos;
  "Cookable now" toggle (Phase 5); mono results summary + colour legend + clear filters.

---

# PART VII — PROMPT v2 (exact changes to `ai/prompts/extract_recipe_details.txt`)

1. Add `mediterranean_categories` and `course` to the LANGUAGE RULES English-only list.
2. Extend the `dish_type` line with `"pasta", "risotto", "pizza", "sandwich", "pastry"`.
3. Append:

```
### Mediterranean categories (English values only):
- **mediterranean_categories**: list of {category, servings, is_oily_fish} objects.
  Categories: "fish", "legumes", "poultry", "eggs", "dairy", "red_meat", "processed_meat".
  Rules:
  - A recipe may count toward MULTIPLE categories (lentil-parmesan soup = legumes + dairy;
    carbonara = eggs + processed_meat + dairy).
  - Count a category only when it is a SUBSTANTIAL component (roughly ≥30g per portion or
    central to the dish) — NOT a garnish. Grated parmigiano to finish a pasta: do not
    count dairy. A parmigiana or cacio e pepe: count dairy.
  - servings: 1.0 when the category is a main component of a portion; 0.5 when
    substantial but secondary.
  - Cured and processed meats ALWAYS map to "processed_meat", never "red_meat", and count
    at full weight when they are the backbone of the dish (carbonara, amatriciana, gricia).
  - Italian mappings — be precise:
    * guanciale, pancetta, salsiccia, salame, prosciutto (crudo/cotto), speck, mortadella,
      'nduja, wurstel → "processed_meat"
    * manzo, vitello, maiale (fresh cuts), agnello → "red_meat"
    * pollo, tacchino, coniglio → "poultry"
    * ceci, lenticchie, fagioli, fave, piselli, cicerchie, lupini → "legumes"
    * pesce, frutti di mare, molluschi, crostacei → "fish";
      is_oily_fish=true for: salmone, sgombro, sardine, alici/acciughe, tonno, aringa, trota
    * formaggi, latte, yogurt, ricotta, burrata, mozzarella → "dairy"
    * uova as a main component (frittata, carbonara, shakshuka) → "eggs";
      one egg to bind polpette: do not count.
  - Vegetarian/vegan dishes with no tracked component: empty list [] (daily base).

### Course (Italian meal structure, English field name):
- **course**: one of "antipasto", "primo", "secondo", "contorno", "dolce",
  "lievitati" (bread/pizza/focaccia doughs), "colazione", "other".
  primo = pasta, risotto, zuppe, gnocchi; secondo = meat/fish/egg mains;
  lievitati = anything whose point is the dough.
```

4. `PROMPT_VERSION = "2"` constant in `ai/batch.py`, stamped into every extraction and,
   via promote, into `Recipe.prompt_version`. Update the Batch request JSON schema to
   include both new fields.

---

# PART VIII — PHASE BOARD (execute strictly in order, one task at a time)

### Phase 0 — Clear the desk (~2 evenings)
- [ ] 0.1 Finish the reopened **Recipe Detail missing fields** task (Notion)
- [ ] 0.2 Delete legacy: `src/foodiegram/recipe_extractor.py` (violates shortcode rule),
      `login.html`, `recipe.js`, stale `.cursor/rules`. Add `.env.example`
      (OPENAI_API_KEY, CLOUDINARY_*, DATABASE_URL, BASIC_AUTH_*, INSTAGRAM_* optional)
- [ ] 0.3 DDD restructure per §3 — **pure moves, zero behaviour change**, imports updated,
      scripts still run. Add `tests/test_architecture.py` (import-direction test)
- [ ] 0.4 Replace the stale Cookstagram README intro with the Dispensa brief (§1) +
      runbook placeholder; append the JS conventions (§15) and the D4 boundary rule
      (SQLModel rows never leave storage/) to CLAUDE.md
- **Done when:** all green; repo has the target shape; nothing legacy remains.

### Phase 1 — Categories & grouping data (~3 evenings)
- [ ] 1.1 Enums (§5) + model fields (§6) + `from_extracted` mapping, with unit tests
      (incl. unknown-category-string tolerance)
- [ ] 1.2 Prompt v2 (Part VII); regression test first: apply/promote path preserves
      user edits before any batch runs
- [ ] 1.3 `extract.py submit --all` → `apply` (still writing recipe JSON at this phase —
      the DB doesn't exist yet). **Keep `batch_output.jsonl` v2** for the Phase-2 backfill
- [ ] 1.4 `review_categories.py` first version (pydantic-ai, against JSON store);
      hand-check the classics: carbonara (eggs+processed+dairy), ragù, pasta e ceci,
      parmigiana, a salmon dish (oily flag)
- **Done when:** every `is_recipe=true` recipe has `prompt_version="2"`; ≥95% of recipes
  with a clear protein have ≥1 category; zero user edits clobbered.

### Phase 2 — Storage: DB as source of truth (~5–6 evenings) — HIGH-RISK PHASE, see §19
- [ ] 2.1 `sqlmodel` dependency; `storage/db.py`; all tables (§10); targets seeding
- [ ] 2.2 `Extraction`, `edited_fields`, `RecipeSource`, nullable IG fields;
      `domain/editing.py` + `domain/diffing.py` with exhaustive tests
      (**promote-respects-edits is the anchor deliverable of this phase**)
- [ ] 2.3 DB-backed `RecipeRepository`; `recipes_json.py` demoted to import/export
- [ ] 2.4 Scripts per §12: `ingest`, `extract` (extractions-only apply), `diff_batch`,
      `promote`, `export`, `import_json` (+ user_state migration inside it)
- [ ] 2.5 Load local DB: `import_json data/recipes/` + backfill `extractions` from the
      kept v2 `batch_output.jsonl`; run `export.py` and initialise the private data repo
- [ ] 2.6 README runbook (§13) finalised
- **Done when:** app serves from the DB; JSON is import/export only; extraction history
  is populated; a re-promote run changes nothing (idempotence proof).

### Phase 3 — Planner backend (~3 evenings)
- [ ] 3.1 `domain/planning.py` (§8) fully tested: multi-category recipe, slot-not-portion
      counting, under/ok/over boundaries, oily-fish rule, gap ranking
- [ ] 3.2 `domain/pantry.py` + `domain/shopping.py` (§9) tested (synonym matching,
      dedupe, aisle grouping, unknown→altro)
- [ ] 3.3 Plan/pantry/targets endpoints (§11) + Basic-auth middleware (D13)
- **Done when:** `GET /api/plans/{week}` returns plan+balance+suggestions in one payload,
  covered by API tests against sqlite-tmp.

### Phase 4 — Frontend: the wow moment (~5–6 evenings)
- [ ] 4.1 `tokens.css` from Dispensa v3 + AA verification (blocks everything else)
- [ ] 4.2 Scaffold §14; port existing browse/detail/favourites — **feature-parity
      checkpoint** against the old index.html before adding anything new
- [ ] 4.3 Slim `/api/recipes` index + client-side search cache (D12)
- [ ] 4.4 `#week` + `#plan` with live BalancePanel (optimistic update → PUT → rollback),
      GapSuggestions, DayColumn keyboard path, live-region announcements
- **Done when:** you plan a real week and the bars move. Start using it that same week.

### Phase 5 — Pantry-lite + shopping list + deploy (~4 evenings)
- [ ] 5.1 PantryList UI + endpoints; kitchen X/Y on cards & detail; Cookable-now filter;
      "From your kitchen" strip with expiry flags
- [ ] 5.2 Shopping-list view + `data/aisles.json` (static map, ships in repo — it's code,
      not data); post-generate "add these to pantry?" nudge
- [ ] 5.3 Deploy: FastAPI Cloud + Neon integration; env vars (`DATABASE_URL` pooled,
      `BASIC_AUTH_*`, `OPENAI_API_KEY`, `CLOUDINARY_*`); `fastapi deploy`;
      `DATABASE_URL=<neon> import_json` initial load; smoke-test an edit surviving a
      redeploy; custom domain + optional repo/package rename to `dispensa`
- **Done when:** it lives at a URL, data in Neon, backup = export + private-repo commit.

### Phase 6 — Editing & manual recipes (~4 evenings)
- [ ] 6.1 Edit mode on Recipe Detail: all content fields + category editor (chips,
      servings 0.5/1, oily toggle); PATCH sets `edited_fields`; "✎ edited" markers;
      per-field revert (drop from `edited_fields`, re-apply latest promoted extraction)
- [ ] 6.2 Add recipe: structured form (`source=manual`, `m-…` code) + paste-text →
      pydantic-ai preview → save (extraction row kind=`paste`); photo → Cloudinary
- [ ] 6.3 Delete (manual) / archive (instagram) rules (D15/§6)
- **Done when:** you can fix anything and add anything; Instagram is one source among many.

### Phase 7 — AI companion (ONLY after ≥3–4 weeks of real weekly use; design later)
Expiry nudges (a date comparison) → taste profile (favourites/repeats/notes) ranking
`gap_suggestions` → pydantic-ai "draft my week" (targets + pantry + preferences in,
`WeekPlan` out) → engaging new-recipe proposals. **Do not design these now.**

---

# PART IX — WORKING WITH CURSOR

## 18. Method
- One checklist item per Cursor session. Paste: (a) the relevant Part of this document,
  (b) CLAUDE.md. Never paste the whole plan — the specs are sectioned for exactly this.
- Every session ends with the full green gate before commit. No "I'll fix types later."
- Kickoff prompt for 0.3 (template for all structural tasks):

> Read CLAUDE.md and follow every convention (no `**kwargs`, mypy --strict, pure domain,
> ruff ALL, line length 89, one-line imperative docstrings). Restructure `src/foodiegram/`
> into the layout in the pasted §3: create `storage/`, `ai/`, `instagram/`, `images/`,
> `app/` packages; move `repository.py → storage/recipes_json.py`; `_auth.py`,
> `instageram_extractor.py`, `cache_manager.py → instagram/`; batch logic from
> `scripts/extract_recipes.py → ai/batch.py` (script becomes a thin wrapper);
> `prompts/ → ai/prompts/`. Pure moves — zero behaviour change, update all imports, keep
> every script entry point working. Add `tests/test_architecture.py` that fails if any
> module in `domain/` imports from storage, ai, instagram, images, app, or api.
> Done = `ruff check --fix . && ruff format . && mypy . && pytest` all green.

## 19. Known personal failure modes (self-imposed guardrails)
- **Phase 2 is the danger zone**: pure infrastructure, no visible payoff — the historical
  context-switch trigger. Anchor: the promote-respects-edits test. When it's green and
  2.5 loads the data, the phase is DONE. Do not gold-plate the diff tooling.
- **Do not review AI output by vibes**: for every Cursor session touching `domain/`,
  read the tests it wrote before accepting.
- **The wow moment is Phase 4.** Everything in 0–3 exists to make it real. If a task
  doesn't serve it, it goes to Phase 6+ or the deferred list (D16).
- If stalled >2 evenings on one item: shrink the item, don't switch phases.

## 20. Open items (non-blocking)
1. Private data repo name/location (placeholder: `estyxx/dispensa-data`) — needed by 2.5.
2. Notion: mirror Phases 0–7 as sub-tasks under the "Weekly Meal Planner (Mediterranean)
   — v1" epic (Claude can do this on request).
3. Custom domain name — decide at 5.3, not before.
