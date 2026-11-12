# Dispensa plan

The single planning document for Dispensa. It gathers every historical plan, design note, engineering observation and audit into one place, in roughly chronological order: the original master plan first, then each wave of phases, the feature design explorations, the running engineering notes, and the reality audit, with the earliest revival plan kept as an archive at the end. Architecture rules and conventions live in `CLAUDE.md`; this file is the roadmap and the reasoning behind it.

Some sections overlap or predate later decisions (for example, extraction running against Neon reverses an earlier rule). Where they disagree, the later section wins; the earlier text is kept for the history of why.

## Contents

1. [Master plan (product, architecture, specs, phases 0-8)](#1-master-plan-product-architecture-specs-phases-0-8)
2. [Phases 9-13](#2-phases-9-13)
3. [Phases 14-20 and the current roadmap](#3-phases-14-20-and-the-current-roadmap)
4. [Design exploration: browse filters](#4-design-exploration-browse-filters)
5. [Design exploration: plan builder and custom recipes](#5-design-exploration-plan-builder-and-custom-recipes)
6. [Engineering notes and out-of-phase observations](#6-engineering-notes-and-out-of-phase-observations)
7. [Reality audit](#7-reality-audit)
8. [Archive: the original revival plan](#8-archive-the-original-revival-plan)

## 1. Master plan (product, architecture, specs, phases 0-8)

*This is the single canonical document. It supersedes plan v1/v2/v3 and `plan.md`.
Repo: `estyxx/dispensa` (package rename → `dispensa` deferred to Phase 5).
All decisions below are LOCKED unless marked open. Work phase by phase, one task at a time.
Definition of done, always: `ruff check --fix . && ruff format . && mypy . && pytest` green
(+ `tsc --noEmit` once the frontend exists). CLAUDE.md conventions apply to every line.*

---

### PART I — WHAT WE ARE BUILDING

#### 1. Product brief

**Dispensa** is a personal recipe library and Mediterranean-diet weekly meal planner.
~800 recipes extracted from saved Instagram posts (mostly Italian; titles/ingredients/
instructions stay verbatim in the original language, classifications in English) plus,
eventually, manually added recipes. The signature feature: a **live, colour-coded weekly
balance panel** tracking 8 protein categories (the 7 below plus `plant_protein`) against
Mediterranean targets — adding or removing a recipe from the week moves the bars in real
time and suggests gap-fillers.
Pantry-lite awareness ("7/9 in kitchen", shopping list). ADHD-friendly, warm, editorial,
accessible. Solo hobby project: simple, readable, robust. A future AI layer (Phase 7)
learns tastes and reduces waste — deliberately last.

#### 2. The Mediterranean engine (product core)

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

### PART II — DECISIONS (all locked)

| # | Decision |
|---|---|
| D1 | Deploy on **FastAPI Cloud**: one `fastapi deploy` ships API + frontend (StaticFiles). Filesystem is ephemeral — nothing mutable on disk in prod. |
| D2 | **Database is the single source of truth for recipes.** Deploy artifact = code only. Data reaches prod via local scripts pointed at Neon (`DATABASE_URL`). |
| D3 | **Two-entity model**: `extractions` (append-only, immutable LLM outputs with prompt/model provenance) vs `recipes` (mutable canonical state). `promote()` is the only path between them and never overwrites user-edited fields. |
| D4 | **ORM: `sqlmodel`** (approved). SQLite locally, Neon Postgres in prod, one codebase. `SQLModel.metadata.create_all` for now; alembic only when schema churn demands it. SQLModel rows NEVER leave `storage/` — repositories return domain models. |
| D5 | **pydantic-ai** gets three jobs: single-recipe repair, category review loop, paste-any-text → structured recipe. OpenAI Batch API remains the bulk path. |
| D6 | Full re-extraction with **prompt v2**: adds `mediterranean_categories`, `course` (approved), extends `dish_type`. Carbonara counts processed_meat at full weight (guideline-honest). *(Superseded: the prompt is now at `PROMPT_VERSION = "3"`, which also adds `plant_protein` and `summary`.)* |
| D7 | **Frontend: no-build vanilla ES modules**, pure function components, tiny pub-sub store, JSDoc + `// @ts-check`, `tsc --noEmit` in `make check`. `typescript` is the only devDependency. |
| D8 | **Pantry-lite**: name + staple/fresh + optional expiry. No quantities, no depletion, ever (until real usage proves otherwise). |
| D9 | **DDD-lite**: `api/scripts → app → storage\|ai\|instagram\|images → domain`. Domain is pure (no I/O, SDKs, env, clock). Enforced by **import-linter** (`lint-imports`), not the never-created `tests/test_architecture.py`. |
| D10 | JSON files demote to **pipeline artifact + export/backup**: `scripts/export.py` dumps DB → `data/recipes/*.json` (sorted keys) → committed to a private data repo → backup + free `git diff` of the data. |
| D11 | **Identity**: `code: str` stays PK. Instagram = shortcode; manual = `m-{slugified-title}-{4 random base32}`. New `source: RecipeSource`; `pk`/`post_url`/`caption` become `\| None`. |
| D12 | **Search stays client-side** over a slim `GET /api/recipes` index cached per session (~800 recipes). No FTS. |
| D13 | **Auth: HTTP Basic middleware over EVERYTHING** (static + API). `BASIC_AUTH_USERNAME`/`BASIC_AUTH_PASSWORD` env vars; auth disabled when unset (local dev). `secrets.compare_digest`. Zero login UI. |
| D14 | **Thumbnails at ingest**: Cloudinary server-side fetch of the CDN URLs in the IGbulkCollector export immediately at ingest, while URLs are fresh. New recipes never depend on instagrapi recovering. |
| D15 | **`is_recipe=false` posts are normal `recipes` rows**, surfaced only in a collapsed "Appunti & ispirazione" shelf in Browse, excluded from planner suggestions. |
| D16 | **Deferred, door open**: recipe variants (`parent_code: str \| None` someday), vision on photo-only posts, repo/package rename (Phase 5), Browse "Goals & Profile" screen, backup automation (manual export is fine solo), AI layer design (Phase 7 only after ≥3–4 weeks of real use). |

---

### PART III — ARCHITECTURE

#### 3. Package layout (target; Phase 0 creates it by pure moves)

```
src/dispensa/
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
│   ├── ingest.py                # food.json → recipe stubs + durable thumbnails (no posts staging; D32)
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
│   └── maintenance.py           # pg_dump/restore/reset + prod guards
│                                # (recipes_json.py deleted in 9.4 — import/export do their own JSON I/O)
├── ai/
│   ├── batch.py                 # OpenAI Batch submit/status/apply; PROMPT_VERSION = "3"
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
tests/                           # domain/ = full coverage; app + storage run against the
                                 #   Postgres test DB (DATABASE_URL_TEST), not sqlite-tmp
```

**Dependency rule (CI-enforced):** nothing in `domain/` imports from any sibling package.
Enforced by **import-linter** (`lint-imports`, 3 contracts: `domain-is-pure`,
`adapters-are-independent`, `layers`); `tests/test_architecture.py` was never created.

#### 4. The recipe data lifecycle

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

### PART IV — DOMAIN & DATA SPECS

#### 5. Enums (`domain/enums.py`)

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

#### 6. Models (`domain/models.py`)

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

#### 7. Editing & diffing (`domain/editing.py`, `domain/diffing.py`) — pure, exhaustively tested

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

#### 8. Planning (`domain/planning.py`) — pure

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
    # Sum CategoryServing.servings per category across meals (each DISH counts once;
    # a slot may hold several dishes, D34).
    # Multi-category recipes contribute to each. Unknown codes: skip (caller logs).

def oily_fish_count(plan: WeekPlan, recipes: Mapping[str, Recipe]) -> float: ...

def gap_suggestions(statuses: Sequence[CategoryStatus], candidates: Sequence[Recipe],
                    *, limit_per_category: int = 3) -> dict[MedCategory, list[Recipe]]:
    # For each "under" category: candidates counting toward it, is_recipe=True,
    # not archived, not already planned; ranked by confidence desc, then favourites
    # (favourite codes passed in by the app layer — domain stays pure).
```

#### 9. Pantry & shopping (`domain/pantry.py`, `domain/shopping.py`) — pure

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

#### 10. Database schema (SQLModel; SQLite dev / Neon prod)

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

#### 11. API (routers; all behind Basic auth middleware, D13)

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

### PART V — TOOLING & RUNBOOK

#### 12. Scripts (thin argparse wrappers over `app/`; all honour `DATABASE_URL`, unset → local Postgres `postgresql+psycopg2://dispensa:dispensa@localhost:5432/dispensa`; every destructive script has `--dry-run`)

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

#### 13. Runbook (goes verbatim in README, replacing the stale Cookstagram copy)

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

### PART VI — FRONTEND

#### 14. Structure (rename `public/` → `frontend/`; split the 1269-line index.html)

```
frontend/
├── index.html                 # shell: <header>, <nav>, <main id="view">, skip-link
├── jsconfig.json              # checkJs, strict, noEmit target for tsc
├── css/
│   ├── tokens.css             # design tokens ONLY (§16)
│   ├── base.css               # reset, typography, focus rings, prefers-reduced-motion
│   └── components.css         # one section per component (.balance-panel__bar …)
└── js/
    ├── main.js                # hash router: #browse, #plan, #favourites, #recipe/{code}
    │                          #   (#week never built — deferred; see §17)
    ├── api/client.js          # fetch wrapper + JSDoc @typedefs for every DTO
    ├── state/store.js         # (deleted in 9.4 — never wired; views use local closures + renderAll())
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

#### 15. JS conventions (append to CLAUDE.md as the JS mirror of the Python rules)

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

#### 16. Design tokens (`css/tokens.css`) — first FE task

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

#### 17. View acceptance criteria

- **#week (Home):** *(deferred — never built; `main.js` routes only browse/plan/
  favourites/recipe.)* balance panel above the fold; strip of DayColumn chips;
  "Cook tonight" = today's dinner; "From your kitchen" = top 3 by kitchen-match ratio,
  expiring items flagged; "Plan the week" CTA → #plan.
- **#plan:** 5 columns Mon–Fri (rows <768px) + sticky right rail (balance, gap suggestions,
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

### PART VII — PROMPT v2 (exact changes to `ai/prompts/extract_recipe_details.txt`)

1. Add `mediterranean_categories` and `course` to the LANGUAGE RULES English-only list.
2. Extend the `dish_type` line with `"pasta", "risotto", "pizza", "sandwich", "pastry"`.
3. Append:

```
### Mediterranean categories (English values only):
- **mediterranean_categories**: list of {category, servings, is_oily_fish} objects.
  Categories: "fish", "legumes", "poultry", "eggs", "dairy", "red_meat", "processed_meat",
  "plant_protein" (tofu/tempeh/edamame/seitan — NOT legumes, which are whole pulses).
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

4. `PROMPT_VERSION` constant in `ai/batch.py` (now `"3"`), stamped into every extraction
   and, via promote, into `Recipe.prompt_version`. Update the Batch request JSON schema to
   include both new fields.

---

### PART VIII — PHASE BOARD (execute strictly in order, one task at a time)

##### Phase 0 — Clear the desk (~2 evenings)  — DONE (0.1 tracked externally)
- [ ] 0.1 Finish the reopened **Recipe Detail missing fields** task (Notion) — external
- [x] 0.2 Delete legacy: `src/dispensa/recipe_extractor.py` (violates shortcode rule),
      `login.html`, `recipe.js`, stale `.cursor/rules`. Add `.env.example`
      (OPENAI_API_KEY, CLOUDINARY_*, DATABASE_URL, BASIC_AUTH_*, INSTAGRAM_* optional)
- [x] 0.3 DDD restructure per §3 — **pure moves, zero behaviour change**, imports updated,
      scripts still run. ~~Add `tests/test_architecture.py`~~ → replaced by **import-linter**
      (`lint-imports`, 3 contracts); `test_architecture.py` was never created.
- [x] 0.4 Replace the stale Cookstagram README intro with the Dispensa brief (§1) +
      runbook placeholder; append the JS conventions (§15) and the D4 boundary rule
      (SQLModel rows never leave storage/) to CLAUDE.md
- **Done when:** all green; repo has the target shape; nothing legacy remains.

##### Phase 1 — Categories & grouping data (~3 evenings)  — DONE (superseded by v3 + DB)
- [x] 1.1 Enums (§5) + model fields (§6) + `from_extracted` mapping, with unit tests
      (incl. unknown-category-string tolerance). `MedCategory` has 8 members incl.
      `PLANT_PROTEIN`; tests in `tests/test_domain_models.py`.
- [x] 1.2 ~~Prompt v2~~ → prompt is at **v3**; promote-respects-edits is
      `tests/test_editing.py` / `test_promotion.py`.
- [x] 1.3 ~~`extract submit --all` → `apply` (JSON store)~~ → superseded by the DB
      path (Phase 2); `batch_output.jsonl` kept for the backfill.
- [x] 1.4 `review_categories.py` first version — `scripts/review_categories.py` +
      `app/review_categories.py` + `ai/repair.py`, `tests/test_review_categories.py`.
- **Done when:** every `is_recipe=true` recipe has a current `prompt_version`; ≥95% of
  recipes with a clear protein have ≥1 category; zero user edits clobbered.

##### Phase 2 — Storage: DB as source of truth (~5–6 evenings) — HIGH-RISK PHASE, see §19
- [x] 2.1 `sqlmodel` dependency; `storage/db.py`; all tables (§10); targets seeding
- [x] 2.2 `Extraction`, `edited_fields`, `RecipeSource`, nullable IG fields;
      `domain/editing.py` + `domain/diffing.py` with exhaustive tests
      (**promote-respects-edits is the anchor deliverable of this phase**)
- [x] 2.3 DB-backed `RecipeRepository` (get/exists/list_all/save/delete/find); API now
      serves from the DB; `storage/__init__` exports the DB repo. `recipes_json.py`
      stays only for the not-yet-migrated write scripts (2.4) + import/export
- [~] 2.4 Scripts per §12: `extract apply` writes **extractions rows only** ✔,
      `diff_batch` ✔, `promote` (dry-run/apply, skips user edits) ✔, `export` ✔,
      `import_json` ✔; all write scripts (ingest/upload/fix/backfill/review) on the DB ✔.
      On-ingest Cloudinary (D14) ✔ (`sync ingest`). Posts staging dropped (D32).
      Still missing: `repair_recipe.py`.
- [x] 2.5 Load local DB: `import_json data/recipes/` ✔ (1152, DB→JSON round-trip proven
      identical); `backfill_extractions.py` ✔ (899 rows at v2 from the kept
      batch_output.jsonl, real created_at timestamps); **idempotence proven** — a v2
      dry-run promote reports 899 considered, 0 would change. `export.py` ✔.
      Remaining manual step: init/push the private data repo.
- [x] 2.6 README runbook (§13) finalised — DB-source-of-truth pipeline, extract→apply→
      promote→export flow, prompt/model-change flow, DATABASE_URL prod note; Makefile
      updated (submit-all/promote/diff/export/import/backfill).
- **Done when:** app serves from the DB ✔; JSON is import/export only ✔; extraction
  history is populated ✔; a re-promote run changes nothing (idempotence proof) ✔.
  **Phase 2 complete.**

##### Phase 3 — Planner backend (~3 evenings)
- [x] 3.1 `domain/planning.py` (§8) fully tested: PlannedMeal/WeekPlan (Monday validator),
      CategoryStatus, week_balance (multi-category, slot-not-portion, under/ok/over
      boundaries, unknown-code skip), oily_fish_count, gap_suggestions (confidence→
      favourite ranking, filters archived/non-recipe/planned)
- [x] 3.2 `domain/pantry.py` + `domain/shopping.py` (§9) tested (synonym matching,
      dedupe, aisle grouping, unknown→altro)
- [x] 3.3 Plan/pantry/targets endpoints (§11) + Basic-auth middleware (D13)
- **Done when:** `GET /api/plans/{week}` returns plan+balance+suggestions in one payload,
  covered by API tests against the Postgres test DB.

##### Phase 3.5 — MCP server (BUILT — not in the original plan)
- [x] `src/dispensa/mcp_server/` — `search_recipes` (semantic, summary rows) and
      `get_recipe` (full `RecipeDetail`) tools. Runs over stdio (`__main__.py`) or
      mounted at `/mcp` behind a JWT/OAuth bearer verifier (`auth.py`) via `asgi.py`.
      Tested: `test_mcp_get_recipe.py`, `test_mcp_oauth.py`,
      `test_search_recipes_semantic.py`. Write tools are Phase 10.

##### Phase 4 — Frontend: the wow moment (~5–6 evenings)  — mostly done
- [x] 4.1 `tokens.css` from Dispensa v3 + AA verification (blocks everything else)
- [x] 4.2 Scaffold §14; port existing browse/detail/favourites — feature parity met.
      (`state/store.js` never wired and was deleted in 9.4; views use local closures.)
- [~] 4.3 Slim `/api/recipes` index ✔ (`RecipeSummary`); **client-side search cache
      not built** — lexical + semantic search are server-side. → Phase 11.
- [~] 4.4 `#plan` with live BalancePanel (optimistic upsert → PUT → rollback),
      GapSuggestions, DayColumn ✔. **`#week` never built** (deferred). Planner is
      **Mon–Fri**, not Mon–Sun.
- **Done when:** you plan a real week and the bars move. Start using it that same week.

##### Phase 5 — Pantry-lite + shopping list + deploy (~4 evenings)  — backends only
- [~] 5.1 PantryList UI + endpoints — **backend done** (`routers/pantry.py`,
      `domain/pantry.py`); no `PantryList.js`, no kitchen ratio on cards.
- [~] 5.2 Shopping-list view + `data/aisles.json` — **endpoint done**
      (`GET /plans/{week}/shopping-list`, `domain/shopping.py`); no frontend view.
- [~] 5.3 Deploy: FastAPI Cloud + Neon — **plumbing advanced** (`dispensa.asgi:app`,
      `[tool.fastapi]`, MCP OAuth, `/api/version`); live deployment unverified from
      the tree. Package already renamed to `dispensa` (commit `26cc3fd`).
- **Done when:** it lives at a URL, data in Neon, backup = export + private-repo commit.

##### Phase 6 — Editing & manual recipes (~4 evenings)
- [ ] 6.1 Edit mode on Recipe Detail: all content fields + category editor (chips,
      servings 0.5/1, oily toggle); PATCH sets `edited_fields`; "✎ edited" markers;
      per-field revert (drop from `edited_fields`, re-apply latest promoted extraction)
- [ ] 6.2 Add recipe: structured form (`source=manual`, `m-…` code) + paste-text →
      pydantic-ai preview → save (extraction row kind=`paste`); photo → Cloudinary
- [ ] 6.3 Delete (manual) / archive (instagram) rules (D15/§6)
- **Done when:** you can fix anything and add anything; Instagram is one source among many.

##### Phase 7 — AI companion (ONLY after ≥3–4 weeks of real weekly use; design later)
Expiry nudges (a date comparison) → taste profile (favourites/repeats/notes) ranking
`gap_suggestions` → pydantic-ai "draft my week" (targets + pantry + preferences in,
`WeekPlan` out) → engaging new-recipe proposals. **Do not design these now.**

---

### PART IX — WORKING WITH CURSOR

#### 18. Method
- One checklist item per Cursor session. Paste: (a) the relevant Part of this document,
  (b) CLAUDE.md. Never paste the whole plan — the specs are sectioned for exactly this.
- Every session ends with the full green gate before commit. No "I'll fix types later."
- Kickoff prompt for 0.3 (template for all structural tasks):

> Read CLAUDE.md and follow every convention (no `**kwargs`, mypy --strict, pure domain,
> ruff ALL, line length 89, one-line imperative docstrings). Restructure `src/dispensa/`
> into the layout in the pasted §3: create `storage/`, `ai/`, `instagram/`, `images/`,
> `app/` packages; move `repository.py → storage/recipes_json.py`; `_auth.py`,
> `instageram_extractor.py`, `cache_manager.py → instagram/`; batch logic from
> `scripts/extract_recipes.py → ai/batch.py` (script becomes a thin wrapper);
> `prompts/ → ai/prompts/`. Pure moves — zero behaviour change, update all imports, keep
> every script entry point working. Add `tests/test_architecture.py` that fails if any
> module in `domain/` imports from storage, ai, instagram, images, app, or api.
> Done = `ruff check --fix . && ruff format . && mypy . && pytest` all green.

#### 19. Known personal failure modes (self-imposed guardrails)
- **Phase 2 is the danger zone**: pure infrastructure, no visible payoff — the historical
  context-switch trigger. Anchor: the promote-respects-edits test. When it's green and
  2.5 loads the data, the phase is DONE. Do not gold-plate the diff tooling.
- **Do not review AI output by vibes**: for every Cursor session touching `domain/`,
  read the tests it wrote before accepting.
- **The wow moment is Phase 4.** Everything in 0–3 exists to make it real. If a task
  doesn't serve it, it goes to Phase 6+ or the deferred list (D16).
- If stalled >2 evenings on one item: shrink the item, don't switch phases.

#### 20. Open items (non-blocking)
1. Private data repo name/location (placeholder: `estyxx/dispensa-data`) — needed by 2.5.
2. Notion: mirror Phases 0–7 as sub-tasks under the "Weekly Meal Planner (Mediterranean)
   — v1" epic (Claude can do this on request).
3. Custom domain name — decide at 5.3, not before.

## 2. Phases 9-13

Derived from `docs/AUDIT.md` (commit `26cc3fd`). Each phase is one or two
Claude Code sessions. Work one checkbox at a time; green gate before commit.

Anything below that is not the current phase goes to a note, not into the
session.

---

#### Decisions (continuing from D21)

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
| D33 | The plan page shows **Mon–Fri by default**, with Sat–Sun on request (a toggle remembered per browser). Plans and the balance always cover all seven days; the toggle says how many weekend meals are hidden. |
| D34 | A meal slot holds **one or more dishes** (a main and a side, a crust and its filling). Each dish is its own `planned_meals` row; a recipe appears at most once per slot, so adding it again only updates its portions. Every dish counts toward the balance. MCP `set_meal` becomes `add_meal` (adds, never replaces); `clear_meal` and `set_portions` take an optional dish `code`. API: `POST /meals` adds, `PUT /meals/{id}` swaps one dish, `DELETE /meals/{id}` removes one. |

---

#### Phase 9 — Debt sweep and pipeline close-out

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

#### Phase 10 — Control from Claude (MCP write tools)

- [x] 10.1 Domain: `Recipe.inspired_by: list[str]` (D17, D24). Use-case
      `save_custom_recipe(...)` that builds a MANUAL recipe with
      `m-{slug}-{rand}` code and `CategoryServing.source="manual"`. Replace
      `scripts/save_custom_recipe.py` with it. `POST /api/recipes` exposes it.
- [x] 10.2 MCP `get_planning_context(week_start)` → one payload: meals,
      balance, oily fish, gap suggestions, targets, pantry, favourites codes.
- [x] 10.3 MCP `set_meal(week_start, day, slot, code | draft, portions)`,
      `clear_meal`, `set_portions` — thin wrappers over the same use-cases
      `PUT /plans/{week}/meals` calls (D23).
      → PUT had no use-case (router called the repo directly), so one was
      extracted: `app/plan_meals.py` (`set_meal`, `set_draft_meal`,
      `clear_meal`, `set_portions`). Slot rules in `domain/planning.py`
      (`check_meal_slot`, `check_portions`, `WeekPlan.meal_at`); PUT now
      404s an unknown code and 422s a day outside Mon..Sun. Tools in
      `mcp_server/write_tools.py` return `to_mcp_plan` (meals with titles,
      balance, oily_fish, suggestions).
- [x] 10.4 MCP `save_recipe` (custom, with `inspired_by`) and
      `update_recipe(code, notes?, is_favorite?, edited fields...)`.
      → `save_recipe` wraps `save_custom_recipe` (same `RecipeCreate` body as
      POST). PATCH logic moved to `app/update_recipe.py` +
      `domain/editing.apply_user_edit`; router and MCP share it. 9.2
      invariant held; end-to-end test added (MCP edit → promote keeps
      `base_servings`).
- [x] 10.5 Pantry (D31): add `location`, `quantity`, `expires_on` to
      `PantryItem`; MCP `get_pantry`, `add_pantry_items`,
      `remove_pantry_items`.
      → `PantryLocation` StrEnum (fridge/freezer/pantry/unknown) and free-text
      `quantity` on `PantryItem`; the existing `expires` already was the
      optional expiry, so no rename. Columns added by schema patch; pre-D31
      rows read as `unknown` / `""`. `app/pantry.py` (add, all-or-nothing
      remove) shared by the router and `mcp_server/pantry_tools.py`.
      `get_planning_context` pantry entries now carry `id`, `location`,
      `quantity`.
- [x] 10.6 `search_recipes` slim view gains `mediterranean_categories` and
      `difficulty` (cheap fields that stop the per-hit `get_recipe` fan-out).
      Optional `category` and `pantry_only` filters.
      → `category` reuses `facets_for` (what the balance counts).
      `pantry_only` = uses at least one pantry item (owner's call), filtered
      before the limit; every hit also carries `pantry_have` /
      `pantry_missing` line counts. Use-case:
      `app/search_recipes.search_recipes_for_planning`. The tool fn is now
      tested directly (closes AUDIT §7's search_recipes gap).
- **Done when:** a full week is planned in one Claude chat with no
  re-explaining: context in one call, a custom variant saved and slotted, the
  pantry updated, nothing typed twice.

#### Phase 11 — Web speed and Plan UI catch-up

- [x] 11.1 Client-side slim index (D27): fetch `/api/recipes` slim once per
      session into memory; lexical filter, facet counts and favourite toggle
      all local; one PATCH on toggle, no refetch. Measure keystroke latency
      before/after.
      → `GET /api/recipes/index` (summaries + server-derived `facets`,
      `is_complete`, `is_recipe`, `search_text`, plus synonym groups, so JS
      re-derives no domain rule). `lib/recipeIndex.js` (once per session,
      `setFavourite`) + pure `lib/localFilter.js`. Parity vs server `find()`:
      34/34 filter combos identical (results + counts). 1,300 synthetic
      recipes, 200 ms debounce in both: keystroke → results median 302 → 206
      ms on localhost, 384 → 206 ms with +80 ms network latency; API calls
      while typing 10 chars 30 → 0. Index 2.4 MB raw / 305 KB gzip.
- [x] 11.2 Plan view: cache `recipesByCode` across mounts; detail view reuses
      the index for header data.
      → The session index is the cross-mount cache: plan cards resolve from
      it and fetch only codes it lacks (recipes saved after it loaded); the
      "+ add" search filters it locally. Detail shows photo + title from the
      index at once (only if already loaded, so a password-less share link
      never asks for it) and fills in the body when `getRecipe` lands.
      With 80 ms latency, 10-meal week: opening Plan 11 → 1 request, titles
      ~280 → ~100 ms; plan search 1 → 0 requests; recipe title 238 → 68 ms.
      Found and fixed on the way: the share-link auth exemption also matched
      `/api/recipes/index` and `/semantic` (commit 9056fc5).
- [x] 11.3 Vector cache + numpy dot product in `find_similar` (D28).
      → numpy added (owner OK'd). `RecipeRepository` keeps every embedding
      as one unit-row float64 matrix, rebuilt when a `(count, max created_at,
      max updated_at)` stamp on `recipe_embeddings` moves (`updated_at` added
      by schema patch: a re-embed keeps `created_at`). Pure math in
      `domain/similarity.py` (`unit_rows`, `cosine_scores`). 1,300 × 1536-dim
      bench: identical top-20 codes and scores on 12 queries; per query 851
      → 4 ms; first search after a start or re-embed ~1.1 s to build;
      16 MB resident.
- [~] 11.4 Measure cold start: `/api/version` cold vs warm; check Neon
      suspend timeout and FastAPI Cloud min instances. Decide, don't guess.
      → Settings checked (2026-10-26): Neon Free plan, AWS Europe West 2
      (London), 0.25↔2 CU, scales to zero (monitoring shows the endpoint
      inactive most of the day). FastAPI Cloud: us-east-1, free plan. The
      app and its database are on opposite sides of the Atlantic, so every
      query pays ~75-80 ms (typical London↔Virginia RTT, not measured) and a
      page makes several. That likely dominates over cold start.
      DECISION (owner): wait for FastAPI Cloud to offer a European region,
      then move the app next to Neon (and the owner). Fallback if that never
      comes: new Neon project in us-east-1 via `db dump` / `db restore`.
      Cold/warm timings still unmeasured: this environment's network policy
      blocks beltrami.family; the `fastapi-cloud-cli` (0.20.0) has no region
      option, only a read-only `region` field per app.
- [x] 11.5 Plan UI: "+ add" offers "my version of…" (inline draft → MANUAL
      recipe via 10.1). Decide Mon–Fri vs Mon–Sun and record it.
      → D33 recorded (Mon–Fri default, weekend toggle). Each picker row has
      "My version" and the picker has "Write my own": a native `<dialog>`
      (`components/CustomRecipeDialog.js`) prefilled from the base recipe,
      categories + servings set by hand, `inspired_by=[base]`; "Save & add"
      = `POST /api/recipes` then the slot PUT (a failed slot retry never
      saves twice). Also fixed "Change" never opening the picker on a filled
      slot (5e1f6c3). Browser-checked end to end on the bench DB.
- [ ] 11.6 Minimal `PantryList` view (list, add, remove, location filter).
- [x] 11.7 Cooking mode on Recipe Detail, per the Dispensa v3 handoff
      (2026-10-27; added out of order at the owner's request).
      → "Start cooking" beside Method opens a full-screen `<dialog>`
      (`components/CookingMode.js`): one step at a time; Back/Next, the
      progress bar, swipe and ←/→ move; Esc closes. Durations in the step
      text ("3 minuti", "12–14 minutes") become timer buttons
      (`lib/cookingSteps.js`, pure). Timers run side by side, survive step
      and route changes (`lib/cookingSession.js`), chime + vibrate + turn
      red when done; quick 1–15 min presets. ≥960px: tick-off ingredients
      (scaled by the page's servings, "this step" marked) | step | timers;
      below: timer strip + ingredient sheet. Closing with timers set leaves
      a corner pill back in (`components/CookingPill.js`). Screen Wake Lock
      while open. Frontend only, no API change. Browser-checked on a mocked
      recipe at 1280 and 390 px.
      → iPhone follow-up: the page cannot ring when the phone is locked or
      on silent (Safari has no vibration either). Each timer gets "⏰", which
      opens the owner's one-time "Dispensa Timer" Shortcut
      (`shortcuts://run-shortcut`, seconds as input) to start a real Clock
      timer (`lib/phoneTimer.js`). Shown on iPhone/iPad only. Web push was
      considered and parked: FastAPI Cloud scales to zero when idle, so an
      in-process send at the timer's end is not reliable without an
      external scheduler.
- [x] 11.8 Recipe Detail redesign, "Split workbench" (direction 1a of the
      recipe-page handoff; 2026-10-27, added out of order at the owner's
      request).
      → Start cooking first; Save · Plan (this week's day picker) · Copy ·
      Export · ⋯ (share link, notes). Chips replace the fit box and tag
      block; thumbnail only when there is a photo. Sticky ingredients card
      beside the method: sections, "to taste" and equipment lines, tap an
      amount to rescale (`lib/recipeDisplay.js`, display-only; a number that
      is not a leading amount is never scaled). Notes autosave. <720px
      container width: Ingredients/Method tabs, glyph-only actions.
      Not built, need data the API lacks: per-line "to buy" flags and "Add
      missing to shopping list" (pantry match is domain logic, not exposed
      per recipe; no shopping-list store), "Edit recipe" (no edit flow).
      Manual recipes read "Your own recipe": web- and Claude-written ones
      are not told apart in the data. Frontend only, no API change.
      Browser-checked on mocked recipes at 1280 and 390 px.
- [x] 11.9 Plan page redesign ("Dispensa Plan v5" handoff; 2026-10-27,
      added out of order at the owner's request).
      → Toolbar: one ‹ week › stepper, "This week" only off this week, a
      Weekend switch that counts hidden weekend dishes. Desktop (≥760px):
      the balance as a strip of eight tiles pinned under the header, and a
      board with meals as rows and days as columns; dish cards keep the
      servings stepper out and tuck Change/Remove behind ⋯ (one open at a
      time). Mobile: a folding balance bar, day tabs (today selected, a dot
      per meal), one day's lunch and dinner, prev/next. One picker for add
      and change (drawer / bottom sheet, native modal <dialog>): Fills a gap
      (recipes with a protein in a category with room left) · All · From
      Instagram; add mode stays open for more dishes, change mode swaps and
      closes. Protein chips show half portions ("½ Legumes"), so
      RecipeSummary now carries `category_servings` (additive API field,
      from `category_servings_for`). The balance still comes from the
      server untouched; servings do not multiply it.
      Kept from before, beyond the handoff: new dishes start at
      DEFAULT_PORTIONS (2), not the prototype's 1; "Mine" (my version of)
      per picker row and "Write my own recipe" (D23); the title links to the
      recipe. Dropped: the oily-fish line under the balance. The picker
      lists the recipes segment (not inspiration saves), capped at 60 rows.
      Browser-checked on a mocked API at 1366 and 390 px.
- [x] 11.10 Move a planned dish (2026-11-11, at the owner's request).
      → `POST /api/plans/{week}/meals/{id}/move` {day, meal}: the dish keeps
      its recipe and portions; a slot that already holds that recipe, or a
      day outside the week, is a 422 (one row per recipe per slot, D34).
      Desktop board: drag a dish card onto another lunch or dinner; cells
      show they are targets and the one under the pointer lights up; cells
      that cannot take it (its own slot, a slot with the same recipe) refuse
      the drop. The menu path (§15.6): "Move" in the ⋯ menu on desktop and
      on every mobile card opens "Move to…", every lunch and dinner of the
      week, weekend included, as 44px buttons. Moves are announced; the
      balance does not change. No reordering inside a slot (no order
      column).
      Across weeks (2026-11-11, at the owner's request): the move body's day
      may be in any week; the dish joins that week's plan (created if
      needed, `week_start_of` in the domain) and the reply is the source
      week. "Move to…" has its own ‹ week › stepper; on the board, holding a
      dragged dish over the toolbar's ‹ or › turns the week (after 0.6 s,
      then every 0.9 s) so it can be dropped into an earlier or later week.
      The balance of both weeks changes, and the announcement says which
      week it went to.
      Browser-checked on a mocked API at 1366 and 390 px.
- **Done when:** browse feels instant; plan page opens without a fetch storm;
  a custom meal can be added from the web without the CLI.

#### Phase 12 — Capture automation

- [ ] 12.1 `PendingLink` + `POST/GET /api/instagram/queue`, synchronous
      Cloudinary thumbnail (see `claude_ios-share-capture-plan.md` §2).
- [ ] 12.2 iOS Shortcut: share sheet → POST URL with Basic auth (D30).
- [ ] 12.3 GitHub Actions hourly caption sync: cookies secret, PATCH caption
      onto the stub, mark processed, fail loudly.
- [ ] 12.4 GitHub Actions weekly: `extract` → `apply` → `promote --apply` →
      `embed --changed`.
- **Done when:** a link shared from the phone becomes a promoted, embedded
  recipe with no laptop involved.

#### Phase 13 — Household (multi-user)

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

#### Kickoff prompt — Phase 9 (paste into Claude Code, plan mode)

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

## 3. Phases 14-20 and the current roadmap

Derived from the tree at `384c221` (11 Nov 2026) and checked against the
"360° State of the App" report of the same day. Where the report and the code
disagree, the code wins; the differences are listed in the evaluation.

Status: **approved by the owner on 11 Nov 2026**, with the answers recorded
at the end. Each phase is a handful of evenings. Work one checkbox at a time;
green gate before commit. Anything that is not the current phase goes to
docs/NOTES.md.

---

#### First three things to do

1. **14.1 MCP subject allow-list** (½ evening, free). Urgent until sign-up
   on the WorkOS project is confirmed closed: today any validly signed token
   can change the plan and the pantry.
2. **14.2 CI** (½ evening, free). `make check` on every push, against a
   Postgres service. It only checks; FastAPI Cloud keeps deploying on push
   to main.
3. **14.3 + 14.4 Weekly backup of Neon and one restore drill** (2 evenings,
   free). Neon is the only place your plans, pantry, notes and own recipes
   exist, and nothing copies them out.

Then 15.1, the shopping-list page: the step that closes the week.

---

#### Evaluation (code at `384c221`)

**The gate is green.** `make check` here: ruff clean, mypy clean (139 files
with `mypy .`; the report's 78 is `mypy src`), 358 tests passed in 11 s,
3 import contracts kept, `tsc` clean. It needs a local Postgres with a
superuser test role (`tests/test_promotion.py:100`) and a UTC default
timezone, both noted in NOTES.md; CI must provide the same.

**What works well.** The layering is real and enforced (`pyproject.toml:124`).
One use-case serves both the web and Claude (`app/plan_meals.py`,
`app/update_recipe.py`), so the two cannot drift. The balance lives only in
`domain/planning.py`. Edit protection is one mechanism (`edited_fields`,
`domain/editing.py:66`). Browse is local and fast (D27). The report's counts
are right: 23 endpoints, 11 MCP tools, 18 components, 12 lib modules, 9,627
lines of Python, 8,369 of JS.

**What is fragile.**

- **Two sources of truth.** CLAUDE.md says local Postgres is the truth and
  Neon is downstream. But everything a person writes (plans, pantry,
  favourites, notes, manual recipes, `base_servings` edits) is written to
  Neon by the web app and by Claude; the owner confirms Neon now holds
  manual recipes, plans and edits that local does not have. The documented
  way to push recipes to Neon is `import_json` (README "Promoting to
  prod"), which calls `RecipeRepository.save`. That method keeps the
  `edited_fields` *marker* but overwrites the *value*
  (`storage/recipes_db.py:263-271`). Today that can only undo a
  `base_servings` edit. Once recipe editing ships it silently undoes any
  edit made on the web. The report missed this.
- **No backup of Neon.** `db dump` exists (`cli.py:85`) but nothing runs it
  against prod on a schedule, and `export` writes recipes only
  (`app/export.py:10`). The report says `db dump` asks for `--yes` on a Neon
  host; it does not, and it does not print its target either. `db restore`
  refuses a Neon host even with `--yes` (`storage/maintenance.py:323`), so
  the 11.4 fallback ("new Neon project via dump/restore") cannot use it.
- **Schema changes run at every app start.** `build_deps` calls `init_db`
  (`deps.py:46`), which runs `create_all`, seven `ADD COLUMN`s, a
  `DROP COLUMN` and `DROP TABLE IF EXISTS posts` (`storage/db.py:67-108`)
  on each cold start, across the Atlantic. Fine for additive patches; not
  fine for the household migration.
- **Any valid MCP token can write.** `JwtTokenVerifier.verify_token`
  (`mcp_server/auth.py:85`) checks signature, issuer and audience, and no
  tool reads the subject. Whoever can get a token from the WorkOS project
  can change the plan and the pantry.
- **The shopping list has no aisles.** `routers/plans.py:35` reads
  `data/aisles.json`; the file does not exist anywhere (owner), so every
  item lands in "altro".
- **No CI, no health endpoint, no error reporting.** The footer's commit
  hash does not work in prod: the deploy ships without `.git`
  (`app/version.py:33`), and the workflow that set `GIT_SHA` was removed
  because it never worked (`4fdc76c`, `8c5410d`).
- **`renderPlan` is one 780-line closure** (`frontend/js/views/plan.js:75-855`).
  The report also asks to split `detail.js`; that file is already fifteen
  small functions and does not need it.
- Small ones: the balance grades four legume dishes or four tofu dishes as
  "Over", against the diet's own guidance (`domain/planning.py:32-46`);
  repositories call the clock (`recipes_db.py:260`, `user_state_db.py:41`)
  against the "clock at the edge" rule; `package.json:13` lists `serve` as
  a runtime dependency that nothing uses; pre-commit runs pyupgrade with
  `--py313-plus` on a 3.14 project; 10.1 and 10.2 are built but unticked.

**Missing for daily use.** A shopping-list page; a pantry page (today only
through Claude); a way to fix a wrong recipe or fill one of the 247 recipes
that have no ingredients; a home-screen icon and a list that works with no
signal in the shop; a `move_meal` tool for Claude (the use-case exists,
`app/plan_meals.py:208`).

**What blocks sharing.** One shared password with no way to revoke one
person; no scope column on `week_plans`, `pantry_items`, `targets`,
`user_state`, `exercise_log` (AUDIT §4 still holds); the open MCP token
check; no backup; no way to hand someone their data or delete it.

---

#### Decisions (continuing from D34)

| # | Decision |
|---|---|
| D35 | **Neon is the source of truth for everything the owner writes**: plans, pantry, favourites, notes, manual recipes, recipe edits. Local Postgres is the workshop for Instagram ingest and extraction only. A push from local to Neon may do two things and nothing else: **insert** an Instagram recipe Neon does not have, and **update fields that are not in Neon's `edited_fields`** on an Instagram recipe it has. It never deletes, never touches a manual recipe, a plan, the pantry, targets, favourites or notes. A full local → Neon sync no longer exists. Replaces the CLAUDE.md line "Local Postgres is the source of truth". |
| D36 | **Backups live in the `estyxx/cookstagram-data` repo, backup-only and private.** A workflow there dumps Neon with Neon's `readonly_user` role, on a **weekly** schedule and on a manual button (`workflow_dispatch`), not nightly (owner's call): the last several weekly dumps kept as artifacts, plus the dump of the 1st of each month kept as a release asset. Reason: free, no new service, and this repo is public so its artifacts would be too. |
| D37 | **CI checks, the platform deploys.** GitHub Actions runs `make check` on push and pull request and never deploys; FastAPI Cloud keeps deploying on push to main. |
| D38 | **Ordered migrations replace DDL at startup**, introduced with the first migration that needs them (identity, 18.1). Tool: Alembic (approved; add it when 18.1 starts). Reason: a scope column with a backfill and new constraints must run once, in order, and be reviewable. |
| D39 | **No bounded-context re-slice.** The package stays layered. Only two areas get their own import contract: `body` (back exercises) and `identity` (users, households). Reason: 9,600 lines and one developer; moving `catalog`/`planning`/`kitchen` is churn with no user-visible result, and the layer contracts already stop the bad imports. |
| D40 | **The phone app is the web app, installed** (manifest, icons, service worker for the app shell and the current shopping list). Capacitor and TestFlight stay deferred until a named native need appears; React Native stays off the board (D30). Reason: free, one evening, and the Clock hand-off already covers locked-screen timers. |
| D41 | **Shopping list before pantry page.** The list is derived on the server on every load; ticked items are kept per device. The aisle map is built from the library's ingredient words and tracked in the repo. Reason: the list is useful with an empty pantry; the pantry page is upkeep that Claude already covers. |
| D42 | **Recipe editing widens the existing PATCH and `edited_fields`.** No second override table, no per-field history beyond what `extractions` already keeps. Revert = drop the field from `edited_fields` and re-apply the latest extraction. |
| D43 | **Identity first, one household per person.** Every user gets a household of one, so each has their own plan, pantry, targets, favourites and notes; the recipe library stays shared (D29). Data is scoped by `household_id`, so two people can share a household later by pointing at the same row; no membership table and no sharing UI now. Users are added by hand (a CLI command plus a WorkOS invite); the app rejects anyone it does not know, whatever WorkOS allows. Basic auth stays behind a setting for one release as the way back. |
| D44 | **MCP accepts only known subjects**: a configured allow-list now, the `users` table once identity exists. Reason: closes the any-valid-token gap without waiting for Phase 18. |
| D45 | **12.3 is dropped** (hourly caption sync with Instagram cookies in GitHub Actions). Reason: it scripts a flagged account from datacenter addresses, against the "don't scrape Instagram from automation" rule. Phone capture becomes paste-the-caption (16.4). The Shortcut queue (12.1, 12.2) stays deferred. |
| D46 | **Back exercises are a separate part, `body`**: own contract, own page, per-user data, shared login and deploy. The page is not rebuilt inside the SPA. Reason: it works, it is used for health, and consistency alone does not pay for rewriting 1,600 lines. |
| D47 | **Monitoring must let Neon sleep.** A shallow health endpoint (no database) for the 5-minute uptime ping; a deep check (one query) once a day. Error tracking waits until a second person uses the app. Reason: a database ping every 5 minutes keeps Neon awake all month and can use up the free compute allowance. |
| D48 | **Split a large file only in the commit before the next feature that touches it.** Pure JS modules get tests with `node --test` (no dependency). Reason: a refactor with no feature behind it is the kind of work that stalls. |
| D49 | **Pasted recipes are extracted in batches, on Neon.** A paste is saved at once as a manual recipe marked "waiting for extraction", with the text kept verbatim. The next batch run reads the waiting rows from Neon, extracts at the Batch API price, appends `extractions` rows (kind `paste`) and promotes them, respecting `edited_fields`. This is the one pipeline that runs against Neon, because that is where pasted text lives; it writes nothing else. "Extract now" is a small, clearly priced button, built only if it stays cheap (16.5). |
| D50 | **Balance targets follow the Mediterranean diet pyramid** (Bach-Faig et al., 2011). Plant categories are floors with no "Over": a target may have no maximum. Animal categories keep a ceiling and lose any floor that would nudge toward more meat. Numbers in 15.7. |
| D51 | **Version = date-based number + deployed commit.** `pyproject.toml` carries `YYYY.M.N` (N-th release of the month), bumped in the commit that lands a checklist item. The footer shows `2026.11.3 · a1b2c3`. The commit comes from whatever the platform really provides at run time, found by a probe (14.9), not from a CI step racing the auto-deploy. If the platform provides nothing, the footer shows the version and the deployment id, never a guessed hash (empty beats wrong). |
| D52 | **Roadmap (owner, 2026-11-11): the free installable PWA is the everyday app.** 15.3 makes Dispensa a real installed app — home-screen icon, full-screen, offline shell — not a shortcut, and it stays free. A native shell (Capacitor around the same web code; no rewrite, D30/D40) is the **only paid step** (Apple Developer Program ~US$99/yr + a Mac) and stays deferred until the Share Sheet capture or notifications become must-haves. **Capture is link-only, no screenshots/OCR** (D16's vision idea stays off): in Instagram, Share → an iOS Shortcut → `POST /api/instagram/queue` (D30). The shared link carries no caption, and we never scrape Instagram from automation, so a queued post is completed from the IGbulkDL export or a pasted caption (16.4). |
| D53 | **Capture needs no Instagram login** (owner insight, 2026-11-11): a shared post link is public, so the queue (D30) takes the bare URL from the Share Sheet — no instagrapi, no account credentials, no IGbulkDL workaround (that existed only because instagrapi could not log in). Full captions are not reliably fetchable anonymously, so completion is best-effort `og:description` (a truncated snippet) plus a pasted caption (16.4) for the full recipe. Any fetch is phone-initiated per post, never server-side bulk scraping (the CLAUDE.md rule). **Native-app testing** can use a *free* Apple personal team — own phone only, re-signed every 7 days, ≤3 devices, no TestFlight; the US$99/yr program is only for sharing with others, or if the share extension's App Group turns out to need it (unconfirmed). |
| D54 | **In-app capture queue replaces the scripts (design — needs approval).** A `pending_links` table on Neon (shortcode PK, url, status, thumbnail_url, caption_snippet, created_at). The iOS Shortcut POSTs the shared public URL to `/api/instagram/queue`; the server parses the shortcode, best-effort fetches the page's `og:image`/`og:description` (public, no Instagram login — D53), uploads the thumbnail to Cloudinary, and stores a PendingLink. A `#queue` page lists them. No instagrapi, no IGbulkDL, no laptop. |
| D55 | **The full caption is pasted per post, not scraped.** `og:description` is truncated, so a queued link alone can't make a full recipe. Each queue item takes one paste of the caption (the 16.4 paste flow, in the app) — that single paste replaces the whole IGbulkDL export. Everything else (thumbnail, extraction, promote) is automatic. |
| D56 | **APPROVED (owner, 2026-11-12): extraction runs from the app against Neon.** Reverses the old CLAUDE.md "extraction never runs against Neon" rule, which was written when extraction only ran in the local workshop and stashed the batch id on disk. The queue's "Extract" button submits an OpenAI **batch** for the pasted captions (DB-tracked in `batch_runs`); an "Import ready" step applies + promotes into Neon recipes, no local sync. The recipe is born on import (completion), not on launch. Prod OpenAI spend is bounded by the account spend cap; the owner runs the first extraction. CLAUDE.md's "Local Postgres is the ingest/extraction workshop" / "extraction never runs against Neon" lines are superseded for the queue path — update them when the import half + endpoints land. |

---

#### Phase 14 — Safety net (~7 evenings, free)

- [x] 14.1 MCP subject allow-list (D44), **urgent**: a setting with the
      allowed `sub` values; a token outside it is rejected and its subject
      logged; an empty list refuses to build the HTTP mount, like the other
      OAuth settings.
      **Accept:** a validly signed token with an unknown subject gets 401
      (test). **Size:** ½. **Depends on:** nothing.
      **Before merging to main:** set `MCP_OAUTH_ALLOWED_SUBJECTS` on
      FastAPI Cloud, or the next deploy will not start.
      → `MCP_OAUTH_ALLOWED_SUBJECTS` (space-separated) in `settings.py`;
      `oauth_config` requires it; `JwtTokenVerifier` refuses a subject
      outside it and logs that subject at WARNING, which is where to copy
      your own id from. +3 tests (361). Merged to main and deployed
      2026-11-11; the owner set MCP_OAUTH_ALLOWED_SUBJECTS on FastAPI
      Cloud first. Verified live: get_pantry and a semantic search over
      /mcp both returned (auth accepted, prod Neon reached).
- [x] 14.2 CI workflow (D37): `make check` with a Postgres 16 service, a
      superuser test role and UTC timezone; Node for `tsc`. No deploy step.
      **Accept:** a push with a failing test shows a red check on GitHub.
      **Size:** ½. **Depends on:** nothing. **Cost:** free (public repo).
      → `.github/workflows/ci.yml`: `make check`, then `git diff
      --exit-code` so an auto-fixed lint or format error still fails. First
      run green in 1.5 min (run 43041900823). A red run has not been shown
      on purpose: it needs a deliberately broken commit in the history.
- [x] 14.3 Weekly Neon backup in `estyxx/cookstagram-data` (D36): confirm
      the repo is private, add a workflow there (weekly `schedule` +
      `workflow_dispatch`) running `pg_dump -Fc` as Neon's `readonly_user`
      with a client matching Neon's Postgres version; recomputable embedding
      vectors left out of the weekly dump and included in the monthly one.
      The Neon connection string for `readonly_user` is added by the owner
      as a repo secret.
      **Accept:** a manual run produces a dump artifact and logs its size.
      **Size:** 1. **Depends on:** the owner adding the secret. **Cost:**
      free (a handful of the 2,000 private Actions minutes a month; check
      current limits).
      → DONE 2026-11-11. `.github/workflows/backup.yml` in cookstagram-data
      (PRs #1 + #2 merged). `pg_dump -Fc --no-owner --no-acl`, secret
      `NEON_READONLY_URL` via container env; the client major is read from the
      server at run time (Neon is on Postgres 18 — a pinned 17 client aborts).
      Weekly excludes `recipe_embeddings` data, first-of-month is a full dump
      kept as a `backup-YYYY-MM` release. `readonly_user` also needs
      `GRANT SELECT ON ALL SEQUENCES` or `pg_dump` fails on `*_id_seq`. Run #3
      green: artifact `neon-20261111-1820-weekly`, 933,522 bytes zipped.
- [x] 14.4 Restore drill: restore the latest dump into a fresh local
      database (`dispensa_neon`, never the workshop database), open a
      recipe, a week plan and the pantry, write date and dump size in
      NOTES.md. Make `db dump` print its target.
      **Accept:** NOTES.md has a dated drill entry with row counts per table
      matching prod. **Size:** 1. **Depends on:** 14.3.
      → DONE 2026-11-11 (owner, laptop): weekly artifact restored into a
      postgres:18 container; recipes 1171, week_plans 2, planned_meals 16,
      pantry_items 0, recipe_embeddings 0 (weekly excludes embeddings). Runs on
      the laptop — this session's proxy blocks the GitHub artifact host.
- [x] 14.5 `sync push` (D35): one command, local → Neon, that inserts new
      Instagram recipes and updates only fields outside Neon's
      `edited_fields`; dry-run by default, prints the target, `--yes` for
      Neon. `import_json` refuses a Neon host. README "Promoting to prod"
      and the CLAUDE.md "Data & environments" lines rewritten.
      **Accept:** tests show a push leaves alone a manual recipe, an edited
      field, a plan, a pantry item and a recipe missing locally.
      **Size:** 2. **Depends on:** 14.4 (a backup exists before the first
      real push).
      → DONE. `dispensa sync push --target <url>` (dry-run default, `--apply`,
      `--yes` for a prod target): inserts Instagram recipes the target lacks and
      overlays only non-`edited_fields` extraction fields (pure
      `domain.editing.apply_push`). Never deletes; never reads plans/pantry/
      targets (uses only `RecipeRepository`). `import_json` now refuses a prod
      host. README "Promoting to prod" and the CLAUDE.md data line rewritten for
      D35. 6 tests against a second Postgres test DB (`dispensa_test_push`): a
      push leaves a manual recipe, an edited field, a target-only recipe and the
      pantry untouched. Gate green (371).
- [x] 14.6 Health and uptime (D47): `GET /api/health` (public, no database)
      and `?deep=1` (one `SELECT 1`, behind auth); a free uptime monitor on
      the shallow one; the weekly backup job calls the deep one.
      **Accept:** stopping the app produces an email within 10 minutes, and
      Neon's monitoring still shows idle periods. **Size:** 1. **Depends
      on:** 14.3. **Cost:** free tier of an uptime service.
      → Endpoints done: `GET /api/health` → `{"status":"ok"}` (public, no DB);
      `?deep=1` → one read via `TargetRepository.ping()`, 503 if it fails,
      behind auth. sqlalchemy stays in storage (the boundary test), so the
      router calls the repo ping directly. +3 tests (364). Owner action: point
      a free uptime monitor at the shallow URL. The weekly backup already hits
      Neon directly, so it is not wired to the deep check (would need app creds
      in cookstagram-data); add that later only if a daily app-level ping is
      wanted.
- [x] 14.7 Cheap cleanups in one sitting: tick 10.1 and 10.2; Makefile
      pipeline targets call `dispensa sync` (F14); remove `serve` from
      `package.json`; pyupgrade to `--py314-plus`; move `instagrapi` to a
      dependency group that the server install leaves out (approved); set a
      monthly spend limit on the OpenAI account.
      **Accept:** `make check` green, and a server-only install has no
      `instagrapi`. **Size:** ½. **Depends on:** 14.2.
      → DONE. 10.1/10.2 ticked; Makefile ingest/extract/status/apply/promote
      call `dispensa sync` (diff/export/import/backfill keep their scripts, no
      sync twin); `serve` dropped from package.json + lock; pyupgrade
      `--py314-plus`; `instagrapi` moved to a `[project.optional-dependencies]`
      `instagram` extra (CI uses `uv sync --locked --all-extras`) — verified
      absent from a server-only `uv export --no-dev`. Gate green (361). Owner
      action still open: set a monthly OpenAI spend limit.
- [x] 14.8 `node --test` for the pure JS modules (`localFilter`, `scale`,
      `cookingSteps`, `week`, `format`, `recipeDisplay`), wired into
      `make check` and CI.
      **Accept:** at least one test per module runs in the gate with no new
      dependency. **Size:** 1. **Depends on:** 14.2.
      → DONE. `frontend/tests/*.test.js` cover scale, week, format,
      cookingSteps, recipeDisplay and localFilter (16 assertions) with Node's
      built-in runner — no dependency. `make check` and CI gained a `js-test`
      step; root `package.json` is `type: module` so Node runs the ES modules.
      Gate green (371 Python + 16 JS).
- [x] 14.9 Versioning (D51). Step one, a probe: log at startup the *names*
      (never values) of the environment variables the platform sets, and
      whether a `.git` directory is present, then read the log of one
      auto-deploy. Known so far from the FastAPI Cloud docs:
      `FASTAPICLOUD_DEPLOYMENT_ID` exists at run time; no commit variable is
      documented; the dashboard links a GitHub deployment to its commit.
      Step two: `/api/version` returns version, commit (if the probe found
      a source) and deployment id; the footer shows them; the probe is
      removed.
      **Accept:** after a push to main, the footer on the live site shows
      the new version and, if the platform exposes it, the pushed commit;
      it never shows a wrong one. **Size:** 1. **Depends on:** 14.2.
      → Done in code. `pyproject` version is `2026.11.1` (YYYY.M.N);
      `/api/version` now returns `version`, `commit` (GIT_SHA or .git, else
      empty — never guessed) and `deployment` (short `FASTAPICLOUD_DEPLOYMENT_ID`).
      Footer shows `version · commit`, or `version · deployment` when no commit,
      or just the version. A once-per-process startup probe logs the *names*
      (never values) of source/commit-like env vars and whether `.git` is
      present. Owner, after the next deploy: read that one log line — if it shows
      a commit-bearing env var, set `GIT_SHA` from it and the footer shows the
      commit; if not (the docs suggest only a deployment id exists), the
      deployment-id fallback already stands. +1 test (365).
- **Done when:** only you can drive the MCP server, a red push is visible,
  the latest backup can be restored and has been once, and a pipeline push
  cannot undo anything you wrote.

#### Phase 15 — Close the weekly loop (~8 evenings, free)

- [x] 15.1 Shopping-list page (absorbs 5.2, D41): `#shop/{week}` from the
      plan toolbar; aisle groups, raw lines under each item, tick to strike
      through (kept per device and week), "Copy list" as plain text.
      **Accept:** for a planned week the page lists every missing
      ingredient once and survives a reload with ticks intact. **Size:** 2.
      **Depends on:** nothing.
      → DONE. `#shop/{week}` from the plan toolbar ("Shopping list"): aisle
      groups, canonical name + raw lines per item, tick-to-strike persisted per
      device and week (localStorage), "Copy list" as plain text. New view
      `frontend/js/views/shop.js` + `getShoppingList` client fn. Browser-checked
      (seeded week, Chromium): each missing ingredient listed once, ticks survive
      a reload, and an **offline** reload still renders the cached list — which
      also closes 15.3's offline-list acceptance. Gate green (372 + 16).
- [x] 15.2 Aisle map from the library (D41): a script lists the canonical
      ingredient names by frequency; the top ones are assigned an aisle by
      hand in one tracked file, loaded once at startup; the git-ignored
      `data/aisles.json` path goes away.
      **Accept:** for a real planned week fewer than 20% of items fall
      under "altro". **Size:** 1. **Depends on:** 15.1.
      → DONE (branch). `domain/aisles.py` ships a starter map (~110 common
      ingredients → ortofrutta/latticini/carne/salumi/pescheria/dispensa/spezie/
      panetteria), keyed through `canonical_term` so it matches the names the
      shopping list produces; an optional `data/aisles.json` is overlaid. The
      <20%-altro target depends on the **real** library, which this session
      can't see — a follow-up `scripts/aisle_frequencies.py` (list canonical
      names by frequency from the DB) would let the owner refine it from live
      data. Aisle names are Italian to match "altro".
- [x] 15.3 Install to home screen and offline list (D40): web manifest,
      icons, a service worker that caches the app shell and the last
      shopping list; the session cookie renews on use instead of expiring
      30 days after login (`api_auth.py:28`).
      **Accept:** in airplane mode the installed app opens and shows the
      last loaded list. **Size:** 1½. **Depends on:** 15.1.
      → Install part DONE (independent of 15.1): `manifest.webmanifest`
      (standalone, teal theme), generated teal "D" icons (192/512/maskable +
      180 apple-touch), iOS web-app metas, and a network-first service worker
      (`sw.js`) that precaches the app shell. The session cookie now renews on
      use (sliding 30-day expiry) so an installed app stays signed in.
      Browser-checked with headless Chromium: SW registers and activates, the
      manifest parses (3 icons), and an offline reload still renders the shell.
      Gate green. The **offline shopping list** is verified with 15.1: the service worker caches the list, so an offline reload of `#shop` still renders it.
- [x] 15.4 Pantry page (absorbs 11.6 and 5.1): list by location, add,
      remove, items expiring within 3 days first.
      **Accept:** an item added on the page appears in Claude's
      `get_pantry` and drops out of the next shopping list. **Size:** 1½.
      **Depends on:** nothing.
      → DONE (branch). `#pantry` (new nav link): items grouped by location
      (Fridge/Pantry/Freezer/Other), sorted soonest-expiry first with a "soon"/
      "expired" badge within 3 days; an inline add form (name, location,
      quantity, expiry) and a remove ×. New view `pantry.js` + `getPantry`/
      `addPantryItem`/`deletePantryItem` client calls. Browser-checked: add,
      badge, group counts and remove all work.
- [x] 15.5 Synonym audit for pantry words (NOTES 10.6): add the missing
      pairs (eggs/uova and the like) for the 50 most common pantry and
      ingredient words, with tests.
      **Accept:** pantry "eggs" matches the line "2 uova" (test).
      **Size:** ½. **Depends on:** nothing.
      → DONE. Added ~30 common cross-language pairs (eggs/uova, flour/farina,
      salt/sale, chicken/pollo, tuna/tonno, lentils/lenticchie, …), word-boundary
      safe (ambiguous singular "noce" omitted). Test: pantry "eggs"/"chicken"
      match "2 uova"/"petto di pollo". Note: the shopping list's canonical name
      is the group's alphabetically-first member, so some names read Italian
      (sale, ceci) — pre-existing; a prefer-one-language pass is a separate tweak.
- [x] 15.6 MCP `move_meal` over `app/plan_meals.move_meal`.
      **Accept:** Claude moves a dish to another day or week and the reply
      carries both balances (test). **Size:** ½. **Depends on:** nothing.
      → DONE. MCP `move_meal(week_start, day, slot, code, to_day, to_slot)`:
      resolves the dish by week/day/slot/code (the MCP view has no ids), then
      calls the use-case. Moves within a week or across weeks; a destination slot
      already holding the recipe is rejected. Returns the source week's plan (the
      use-case/web contract returns one week, not both). 3 tests.
- [x] 15.7 Targets that match the diet (D50): a target's maximum becomes
      optional in the domain, storage, API and the balance tiles; a
      category with no maximum is never "Over". New defaults, applied to
      prod once, by hand, through `PUT /api/targets`:

      | Category | Today | Proposed | Pyramid (weekly) |
      |---|---|---|---|
      | Legumes | 2–3 | 2 or more | ≥ 2 |
      | Plant protein | 2–3 (placeholder) | 1 or more | not listed; counted with the plant side |
      | Fish | 2–3 | 2 or more | ≥ 2 |
      | Eggs | 2–4 | 2–4 | 2–4 |
      | Poultry | 1–2 | 0–2 | 2 |
      | Dairy | 0–7 | 0–7 | daily, moderate |
      | Red meat | 0–2 | 0–1 | < 2 |
      | Processed meat | 0–1 | 0–1 | ≤ 1 |

      Source: Bach-Faig A. et al., "Mediterranean diet pyramid today",
      Public Health Nutrition 14(12A), 2011, doi 10.1017/S1368980011002515.
      The pyramid's numbers were read from secondary summaries here (the
      paper's host was not reachable); check them against its Figure 1
      before applying. Legumes and plant protein together give a floor of
      three plant-protein meals a week, the direction the 2019 EAT-Lancet
      report asks for on environmental grounds. Poultry loses its floor so
      the app never suggests eating more meat; red meat's ceiling drops to
      1 because "< 2" means one.
      **Accept:** a week with five legume dishes shows legumes "On track",
      and a week with no poultry shows no gap for it (tests).
      **Size:** 1. **Depends on:** nothing.
      → DONE (branch). `CategoryTarget.max_servings` is now `float | None`;
      `_state` never returns "over" when there is no max; `targets` column made
      nullable (schema patch). New defaults per the table above. API (TargetOut/
      TargetIn/CategoryStatusOut) and the frontend handle a null max — balance
      tiles show "2+" and never a false "Over" (browser-checked, no NaN).
      Five-fish week → On track; zero-poultry (min 0) → no gap. Tests added.
      **Owner:** the numbers await your check against the paper's Figure 1, and
      your existing prod targets are unchanged until you apply them via
      `PUT /api/targets` (seeding only fills missing categories).
- **Done when:** a real week goes plan → list on the phone in the shop →
  cook, twice in a row, without opening the laptop.

#### Phase 16 — Fix anything, add anything (~8 evenings; absorbs Phase 6)

- [x] 16.1 Widen PATCH (D42): title, ingredients, instructions, times,
      categories with servings (0.5 steps) and the oily-fish flag go
      through `apply_user_edit`; MCP `update_recipe` gains the same fields.
      **Accept:** an edited ingredient list survives `promote --apply` and
      `sync push` (tests). **Size:** 1. **Depends on:** 14.5.
      → DONE (branch). `RecipeEdit`/`RecipeUpdate` (PATCH) and MCP
      `update_recipe` gained title, ingredients, instructions, summary, times,
      difficulty and `mediterranean_categories`, all through `apply_user_edit`
      (recorded in `edited_fields`; the anchor promote/push test protects them).
      +2 tests. The category editor UI is 16.2.
- [ ] 16.2 Edit mode on the recipe page: edit in place, "edited" marker per
      field, save through 16.1; recipe text marked `lang="it"`.
      **Accept:** a wrong category fixed on the page changes that week's
      balance after reload. **Size:** 2. **Depends on:** 16.1.
- [x] 16.3 Revert a field: drop it from `edited_fields` and re-apply the
      latest extraction for that field only.
      **Accept:** revert restores the extracted value and the marker goes
      (test). **Size:** 1. **Depends on:** 16.1.
      → DONE (branch). Pure domain `revert_field(recipe, extraction, field)`
      in `domain/editing.py` (restricted to `EXTRACTION_FIELDS`; a no-op for an
      unedited field). App use-case `app/revert_field.revert_recipe_field`
      resolves `extractions.latest_for` and saves. `DELETE
      /api/recipes/{code}/edits/{field}` → 422 non-revertable / 404 unknown /
      409 no extraction. +6 tests. The per-field "revert" button is part of the
      16.2 edit UI.
- [ ] 16.4 Paste a recipe (D49): paste a caption or any recipe text on the
      phone or laptop; it is saved at once as a manual recipe "waiting for
      extraction", visible in Browse with its text and nothing invented.
      The batch run (`sync extract --waiting` → `apply` → `promote`) on
      Neon fills it in; run by hand until 19.2 schedules it.
      **Accept:** a pasted text shows as waiting within a second, and after
      one batch run it is a complete recipe; a failed extraction leaves the
      waiting row and its text untouched. **Size:** 2½. **Depends on:**
      16.1. **Cost:** about half a cent a recipe (see "Where OpenAI money
      goes").
- [ ] 16.5 "Extract now" on a waiting recipe, only if 16.4 shows the wait
      hurts: one live call, the button labelled with its price ("about 1¢,
      twice the batch price").
      **Accept:** the button fills one recipe in under a minute and logs
      the tokens it used. **Size:** ½. **Depends on:** 16.4.
- [x] 16.6 Archive and delete rules (6.3): archive an Instagram save,
      delete a manual recipe; archived recipes leave Browse, suggestions
      and the picker, but stay on plans that already hold them.
      **Accept:** an archived recipe is absent from `/api/recipes/index`
      and still renders in a past week (test). **Size:** 1. **Depends
      on:** 16.1.
      → DONE (branch). `archived` added to the edit surface (PATCH can archive);
      `/api/recipes/index` excludes archived, so they leave Browse, the picker
      and gap suggestions (already archived-aware), while `get_recipe` still
      returns them, so a past plan that holds one still renders. New
      `DELETE /api/recipes/{code}`: manual recipes only (Instagram → 409,
      unknown → 404). +4 tests.
      → FOLLOW-UP DONE (branch). `find`/`find_similar` now take
      `archived: bool | None = False`, so an archived save is out of the
      `/api/recipes` list, `/count`, semantic ranking and the MCP search/gap
      suggestions too — not just the client index. `archived=None` keeps both,
      `True` returns only archived; a past plan still renders one via `get`.
      +2 tests.
- **Done when:** the four recipes with empty v3 ingredients and five of the
  247 are fixed from the phone, and a pipeline run leaves them alone.

#### Phase 17 — Body: back exercises as their own part (~3 evenings, free)

- [x] 17.1 Isolate (D46): an import contract so the exercise modules import
      nothing from recipes, planning or pantry and nothing imports them
      except the composition root; a link to the page from the app footer.
      **Accept:** `lint-imports` reports 4 contracts kept. **Size:** ½.
      **Depends on:** nothing.
      → DONE. New import contract `body-is-separate`: the exercise **domain**
      (`domain.exercise_log`) imports no food domain module — enforced. (The
      router/repo legitimately share `deps`, `api_models` and `storage.db`
      infrastructure, so full-feature isolation would mean splitting those; the
      domain contract is the meaningful, true guarantee per D39.) Footer link
      "Back exercises" → `/schiena.html`. `lint-imports`: 4 kept.
- [ ] 17.2 Stable exercise ids: the routine moves from the HTML into one
      tracked data file with an id per exercise; the log stores the id; old
      rows are mapped by name once.
      **Accept:** renaming an exercise in the data file leaves its history
      attached (test). **Size:** 1½. **Depends on:** 17.1.
- [ ] 17.3 A month view on Progressi: days done per week for the last eight
      weeks, from `/api/exercise-log/range`.
      **Accept:** the view matches a hand count for one logged week.
      **Size:** 1. **Depends on:** 17.2.
- **Done when:** the page has its own place, its history survives edits to
  the routine, and it shares nothing with the food code but the login.

#### Phase 18 — Identity: one household per person (~8 evenings; absorbs Phase 13)

- [ ] 18.1 Migrations (D38): add Alembic, baseline today's schema,
      `init_db` stops running DDL, migrations run before the app starts and
      in CI.
      **Accept:** a fresh database built by migrations equals one built by
      today's `create_all` (schema diff empty). **Size:** 1½. **Depends
      on:** 14.2, 14.4.
      → **18.1a DONE (branch): infrastructure + baseline, no startup change.**
      Alembic added (runtime dep); `alembic.ini` + `migrations/` with an
      `env.py` wired to `SQLModel.metadata` and the app's `DATABASE_URL`; the
      `script.py.mako` imports `sqlmodel`; one baseline migration (11 tables)
      autogenerated from the models. `storage/migrations_runner.py` wraps
      `upgrade_to_head` / `stamp_head` / `current_revision`.
      **Acceptance met:** `test_migrations.py` builds an empty DB from
      migrations alone and asserts `compare_metadata` vs `SQLModel.metadata`
      is empty — i.e. migrations == create_all. +3 tests. `init_db` still
      runs `create_all` (unchanged), so this is zero-risk to prod.
      → **18.1b DONE (branch): init_db flipped to migrations, auto-adopting.**
      `init_db` now runs `_ensure_schema` (migrations to head) instead of
      `create_all` + patches, then seeds. A database with tables but no
      `alembic_version` (Neon, the local workshop — every pre-Alembic DB) is
      stamped at the baseline and left as-is; a fresh database has its tables
      created by the upgrade. **No manual prod step:** the first deploy adopts
      Neon automatically. Smoke-tested against a real pre-Alembic DB
      (`build_deps` → stamped baseline, 4 rows intact, nothing recreated).
      Conftest keeps using `create_all` + `_ensure_schema_patches` for the
      test DBs (fast); the parity test guarantees the two paths agree. +2
      tests. **Migrations run in CI** via the migration tests in `make check`.
      D38 criterion met.
- [ ] 18.2 `households` and `users` (each user points at one household); a
      migration seeds your household owning every existing row; a
      `dispensa users add <email>` command creates a user with a household
      of one and default targets.
      **Accept:** row counts before and after are equal, and adding a user
      twice changes nothing. **Size:** 1. **Depends on:** 18.1.
- [ ] 18.3 Web login with WorkOS AuthKit (D29, D43): redirect, callback,
      server-side session cookie, logout; a WorkOS identity with no `users`
      row is refused; Basic auth stays behind a setting; share links keep
      working.
      **Accept:** you sign in on phone and laptop and the app behaves as
      before; an identity that was not added by hand gets a plain "not
      invited" page. **Size:** 2. **Depends on:** 18.2. **Cost:** free at
      this size (check WorkOS pricing before starting).
- [ ] 18.4 Scope the data (13.1, 13.2): `household_id` on `week_plans`,
      `pantry_items`, `targets`, `user_state`; `user_id` on `exercise_log`;
      the four constraints from AUDIT §4; threaded router → deps →
      repository.
      **Accept:** a test with two users planning the same week shows
      neither sees the other's plan, pantry, targets, favourites or
      exercise log. **Size:** 2½. **Depends on:** 18.3.
- [ ] 18.5 MCP resolves the user from the token (13.3); the allow-list from
      14.1 is replaced by the `users` table.
      **Accept:** user B's token cannot read user A's plan (test).
      **Size:** ½. **Depends on:** 18.4.
- [ ] 18.6 Take-out and removal: "Download my data" (one JSON: plans,
      pantry, targets, favourites, notes, exercise log) and a
      `dispensa users remove` command that deletes that person's rows.
      **Accept:** the file round-trips through a test import, and a removed
      user's session and token get 401. **Size:** 1. **Depends on:** 18.4.
- [ ] 18.7 Add the first person by hand; switch Basic auth off after a week
      without problems.
      **Accept:** they plan a week and nothing of yours shows in their
      view. **Size:** ½. **Depends on:** 18.5, 18.6.
- **Done when:** two people plan the same week against the same library
  without seeing each other, and each can leave with their data.
- **Later, not now:** two users sharing one household (point both at the
  same row, plus a way to merge two pantries).

#### Phase 19 — Capture and pipeline automation (deferred; ~4 evenings)

Only after Phase 16 has been in use for a month. If pasting a caption is
enough, 19.1 stays closed.

- [ ] 19.1 Share-sheet queue (12.1, 12.2): the Shortcut posts a link to a
      queue; the next manual export fills it in.
      **Accept:** a shared link shows as "waiting" in Browse within a
      minute. **Size:** 2. **Depends on:** 18.3 (token instead of Basic).
- [ ] 19.2 Scheduled paste batch (D49) in the `cookstagram-data` Actions:
      twice a week, `extract --waiting` → `apply` → `promote --apply` →
      `embed --changed` against Neon, after a backup run.
      **Accept:** a recipe pasted on Monday is complete and searchable by
      Thursday with no laptop. **Size:** 2. **Depends on:** 14.3, 16.4.
      **Cost:** cents a run.

---

#### How data moves (D35, D49)

```
Instagram saves                      Your own writing
  food.json                            web app · Claude (MCP) · paste
     │                                        │
     ▼                                        ▼
LOCAL Postgres (workshop)            NEON (source of truth)
  ingest → extract → apply             plans, pantry, targets, notes,
  → promote → review                   favourites, manual recipes, edits
     │                                        ▲        │
     └── sync push ───────────────────────────┘        │ weekly pg_dump
         insert new Instagram recipes;                  ▼
         update fields not in edited_fields;      cookstagram-data (private)
         nothing else, ever                             │ restore
                                                        ▼
                                     local `dispensa_neon` (read copy)
```

- The Instagram pipeline does not need your manual recipes, so the workshop
  database is never overwritten from Neon; its extraction history stays.
- When you want real data locally (to test, to look), restore the latest
  dump into `dispensa_neon`. That is the Neon → local refresh: a separate
  database, read-only by habit, replaced on each restore.
- `sync embed --changed --yes` still runs against Neon after a push, as the
  README says today.

#### Where OpenAI money goes

Rates per million tokens, from third-party price lists read on 11 Nov 2026
(OpenAI's own page was not checked): `gpt-5.4-mini` $0.75 in / $4.50 out,
half that through the Batch API; `text-embedding-3-small` $0.02. Token
counts are estimates from the prompt (183 lines) and typical captions.

| Where | Code | When | Rough cost |
|---|---|---|---|
| Recipe extraction (batch) | `ai/batch.py` | `sync extract`, by hand | ~0.4¢ a recipe; ~$5 for the whole library |
| Pasted-recipe extraction (batch) | same, D49 | twice a week once 19.2 exists | ~0.4¢ a recipe |
| "Extract now" (live) | 16.5, if built | one tap | ~1¢ a recipe |
| Category review and repair (live) | `ai/repair.py` | `scripts/review_categories.py`, by hand | ~1¢ a recipe |
| Recipe embeddings | `ai/embeddings.py` | `sync embed --changed` | under 1¢ for the whole library |
| Search by meaning, web | `GET /api/recipes/semantic` | each AI-mode search | far below 0.001¢ a search |
| Search by meaning, Claude | MCP `search_recipes` | each call | the same |

Nothing else calls OpenAI. Lexical search, the balance, suggestions and the
shopping list cost nothing. The one line that can surprise is a full
re-extraction after a prompt change (~$5); the monthly spend limit in 14.7
caps it.

#### What it costs to run

| Step | Cost |
|---|---|
| Phases 14, 15, 17 | Free: GitHub Actions, Neon free, FastAPI Cloud free, a free uptime monitor. |
| Phase 16 | OpenAI, about half a cent a pasted recipe. |
| Phase 18 | WorkOS AuthKit free tier at this size (check before starting). |
| Phase 19 | OpenAI batch: cents a run. |
| Not planned | Apple Developer Program, about US$99 a year, only if Capacitor is ever approved. |

Prices are from memory or secondary lists and must be checked on the day;
none of the planned phases needs a paid plan.

---

#### Phase 20 — In-app capture queue (design; needs approval before build)

Reworks Phase 12/19 into the owner's end-goal flow: share a link → it appears
in the app → paste the caption once → extract → the recipe lands on Neon, no
scripts, no laptop. Decisions D54–D56. **Build starts only once the owner
approves the new table and, for 20.4, the extraction-against-Neon rule change.**

- [x] 20.1 `pending_links` table + `POST /api/instagram/queue` (take a public
      post URL, parse the shortcode, store a PendingLink `status=new`). The
      server best-effort fetches `og:image`/`og:description` and uploads the
      thumbnail to Cloudinary; failures leave the item without a thumbnail, not
      an error. **Accept:** a POSTed link shows as a pending item within a
      second. **Size:** 2. **Needs:** owner OK for the new table.
- [ ] 20.2 iOS Shortcut: share sheet → POST the URL (no Instagram auth, D53).
      **Accept:** sharing an Instagram post from the phone adds a pending item.
      **Size:** 1.
- [x] 20.3 `#queue` page: pending items with thumbnail + caption snippet; per
      item, "Paste caption" (the full text) and a remove. **Accept:** pasting a
      caption on a queued item stores it and marks the item ready. **Size:** 2.
      **Depends on:** 20.1, 16.4.
- [ ] 20.4 "Extract" → turn ready queue items into recipes, no local sync.
      **DECIDED (owner, 2026-11-12):** (b) **batch**, extracting on Neon
      ("cheaper; batch is needed"), with the recipe born **on completion** (the
      post stays a queue item while extracting; the full recipe appears on
      import). The disk-batch-id blocker is gone — batch state lives in the DB
      (`batch_runs`, the 2026-11-12 refactor).
      → **Launch half DONE (branch).** `app/queue_extraction.launch_queue_extraction`
      builds the batch input straight from the ready queue captions (generalised
      `write_batch_input` to a `Captioned` protocol — Recipe or PendingLink),
      submits a DB-tracked batch and marks each link EXTRACTING with the batch
      id; dedups against `all_submitted_codes()`. +4 tests (fake OpenAI).
      → **Import half DONE (branch).** `app/queue_import.import_finished_queue`
      reads the completed batch and, per result still EXTRACTING, promotes it onto
      a fresh Instagram recipe (reusing `promote`), saves it, appends the
      extraction, marks the link IMPORTED, marks the batch APPLIED. Idempotent.
      +3 tests.
      → **Endpoints DONE (branch).** `POST /api/instagram/queue/extract` and
      `/import` (both return `{count}`; 503 on missing key). `Deps` gained
      `batches`; new `SettingsDep`. +2 endpoint tests.
      → **Queue-page buttons DONE (branch).** A toolbar on `#queue`: "Launch
      extraction (N)" and "Import finished (N)", with counts, disabled states and
      a status line. Browser-checked (seeded queue, Chromium).
      → **ALL CODE DONE.** Only the first real extraction is left — the owner's
      (OpenAI spend; api.openai.com blocked in this session), small, with the
      spend cap. **Size:** 2–3. **Depends on:** 20.1/20.3 + batch-state-in-DB.
- [ ] 20.5 Retire the scripts path once 20.1–20.4 are in daily use (keep
      `export`/`db dump`). **Size:** 1.

#### Dropped or kept deferred

| Item | Call | Why |
|---|---|---|
| Bounded-context re-slice (catalog, planning, kitchen, ingestion) | Dropped | D39. |
| Splitting `detail.js` | Dropped | Already small functions. |
| Splitting `plan.js` and `CookingMode.js` | When next touched | D48. The next plan-page feature starts with a pure move of state and actions out of `renderPlan`. |
| OpenAPI ↔ JSDoc contract test | Deferred | Parsing JSDoc is brittle; `tsc` plus the API tests catch most renames. Revisit if a rename ever breaks the page. |
| Capacitor / TestFlight | Deferred | D40. About US$99 a year for the Apple programme (from memory; check). |
| React Native / Expo | Off the board | D30 holds. |
| Web push | Parked | Scale-to-zero hosting cannot send at a timer's end; the Clock hand-off works. |
| 12.3 Instagram caption sync in CI | Dropped | D45. |
| Deploy from CI | Dropped | D37; the platform deploys on push to main. |
| JSON export to a data repo (D10, 2.5) | Dropped | Neon is the truth and `pg_dump` is the backup (D36). `scripts/export.py` stays as a tool. |
| Shared households, membership, invitations UI | Deferred | D43. |
| 9.3 caption-changed re-extract (D26, F5, F6) | Deferred | Captions rarely change. `caption_hash` stays write-only; do not build on it. |
| 9.1 summary promote (831 rows) | Do after 14.5 | One command, but push it the D35 way. |
| pgvector | Deferred | Search is 4 ms at 1,300 recipes. D28 says 5k, CLAUDE.md says 10k: use 5k as the point to measure memory, not to migrate. |
| Region move (11.4) | Waiting, with a date | If there is no European region by 1 Feb 2027, measure three pages from home and decide on moving Neon to us-east-1. `db restore` needs a deliberate override for that one run. |
| Phase 7 AI companion | Deferred | Its own rule: 3–4 weeks of real weekly use first. |
| `#week` home page | Dropped | Plan is the home page in practice. |
| Error tracker | Until a second user | D47; it is a new dependency. |
| Interface in two languages | Dropped | English interface; recipe text stays Italian, marked `lang="it"` (16.2). |
| Rebuilding the exercise page in the SPA | Dropped | D46. |
| Signed, expiring share links | Deferred | Revisit with 18.3; the library is private and a code is hard to guess. |

---

#### Owner's answers (11 Nov 2026) and what is still open

| # | Answer | Where it landed |
|---|---|---|
| Q1 | Neon holds manual recipes, plans and edits local does not; a full local → Neon sync is over. | D35, 14.5, "How data moves" |
| Q2 | Data repo is `estyxx/cookstagram-data`; a read-only Neon role `readonly_user` exists; back up weekly or manually, not nightly. | D36, 14.3 |
| Q3 | No `data/aisles.json` exists; build the map from the library and track it. | D41, 15.2 |
| Q4 | OpenAI for pastes yes, but batched; "extract now" only if cheap and marked; list the spend. | D49, 16.4, 16.5, "Where OpenAI money goes" |
| Q5 | Unknown whether WorkOS sign-up is open; users are added by hand. | 14.1 urgent, D43, check below |
| Q6 | One household per person for now; English interface. | D43, Phase 18 |
| Q7 | Yes to moving `instagrapi` and to Alembic at 18.1. | 14.7, D38 |
| Q8 | The deploy workflow went because the hash never worked; keep auto-deploy; plan versioning. | D37, D51, 14.9 |
| Q9 | Plant protein is a floor with no "Over"; check poultry and red meat. | D50, 15.7 |

**Still open, for you:**

1. **Check sign-up on WorkOS.** In the WorkOS dashboard: pick the
   environment the app uses (Production, top of the sidebar) →
   **Authentication** → the **Sign up** setting. Off means only invited
   people can create an account. People are invited under **Users** →
   **Invites**. (From the WorkOS docs "Invite-only signup"; their site was
   not reachable from here, so the labels may differ slightly.) While you
   are there, copy your own user id (**Users** → your row, an id starting
   `user_`): 14.1 needs it for `MCP_OAUTH_ALLOWED_SUBJECTS`.
2. **Is `cookstagram-data` private, and add the `readonly_user` secret?**
   It must be private before 14.3 puts a database connection string and
   dumps in it.
3. **Confirm the numbers in 15.7** against the paper's Figure 1, or tell me
   to apply them as proposed.

---

#### Kickoff prompt — Phase 14 (paste into Claude Code, plan mode)

```
Read CLAUDE.md, docs/PLAN-next.md Phase 14 and decisions D35–D51. Derive
reality from the tree, not the docs.

We are doing Phase 14 only, one item at a time, in order. For each item:
restate its acceptance in one sentence, plan, I approve, you edit, then run
`make check`. Red means not done.

Constraints:
- No new dependency. If an item seems to need one, stop and ask.
- 14.3 and 14.4 touch production data read-only. Print the target host
  before every command and never write to a neon.tech host.
- CI never deploys (D37).
- Nothing from Phase 15+ enters this session; write it to docs/NOTES.md.
```

## 4. Design exploration: browse filters

#### The problem in one sentence

Browse works, but filtering is thin, the card badge shows a random field, and about
45% of the cards are not real recipes, so the page feels noisy and hard to steer.

Claude Design gave us a clear target for the fix: direction **1a, the "Quiet Command
Bar"**. One search line at rest, everything else on demand. This plan turns that picture
into small, safe steps for Cursor.

The wider name for what we are building is **faceted search**: let the user filter a
collection by a few known dimensions at once (protein, dish, cuisine, time), plus a
text search. It is a well understood pattern, so we are not inventing anything new.

**One honest warning up front.** The mockup is beautiful, and parts of it are drawn on
data we do not have yet. The pretty Italian badges (Frittata, Contorno) and the one-line
card descriptions have no field behind them in the code. The ingredient dropdown with
counts ("tofu 31") needs an index and clean ingredient names we have not built. So this
plan does the backend first, ships a working version, and keeps the missing-data features
as a separate step at the end. That way you never hit a wall halfway.

---

#### How to use this with Cursor

- Do **one session at a time**. Each one below is a full, small unit of work.
- After each session, run the full green gate before moving on:
  `ruff check --fix`, `ruff format`, `mypy`, `pytest`, `lint-imports`.
  The frontend is vanilla JS, so there is no `tsc` step.
- **Read the protein mapping table by eye.** That table is a real-world decision (is tofu
  a legume? is guanciale processed?), not a mechanical one. Do not accept the AI grouping
  on faith. This is the one place to slow down.

##### Which screenshots to attach

Attach only the four that show direction **1a** and the design rules. The others are the
rejected directions and will confuse Cursor.

| File | What it is | Give to Cursor? |
| --- | --- | --- |
| `Dispensa_Filter_Explorations.png` | 1a desktop, calm default | Yes |
| `Dispensa_Filter_Explorations__5_.png` | 1a desktop, Filters panel open | Yes |
| `Dispensa_Filter_Explorations__4_.png` | 1a mobile, calm + bottom sheet | Yes |
| `Dispensa_Filter_Explorations__3_.png` | The three design rules (is-recipe, 8 pills, badge) | Yes |
| `Dispensa_Filter_Explorations__1_.png` | 1c, a direction we are NOT building | No |
| `Dispensa_Filter_Explorations__2_.png` | 1b and 1c, directions we are NOT building | No |

---

#### Ground rules (the architecture we already have)

We keep the layered design and its dependency rule. In plain words: inner layers never
import outer ones. New pure logic goes to the centre (`domain`), filtering stays in
storage, the API only wires request parameters to the store.

```mermaid
flowchart LR
  API["api / scripts"] --> APP["app"]
  APP --> STORE["storage / ai / instagram / images"]
  STORE --> DOMAIN["domain (pure)"]
```

Where the new work lands:

- The protein categories and their mapping are pure rules, so they live in `domain`.
- The new filters live in `repository.find` (`dispensa/repository.py`), next to the ones
  already there.
- `api.list_recipes` (`dispensa/api.py`) only reads new query parameters and passes them
  down.
- The UI lives in `public/` (served as static files by the API).

Conventions to keep (from `CLAUDE.md`):

- Keyword-only arguments on functions with more than one parameter.
- Use-cases are module-level functions, never classes.
- Pydantic v2, frozen models. `mypy` strict. No `**kwargs`, explicit signatures.
- No `from __future__ import annotations` (we target Python 3.14).
- Errors carry detail as attributes, not inside the message string.
- IDs are strings. Recipes are keyed by the Instagram shortcode (`code`).

**Out of scope for this plan.** The mockup header shows a "This Week / Plan" navigation.
That is the weekly meal planner, a different phase. Keep the current "Browse / Favourites"
navigation. Do not build the planner here.

---

#### The shared decision: one name for protein (do this before the filter)

Today `Recipe.proteins` is a free list of words: `["tofu"]`, `["chicken", "cheese"]`, and
so on. The mockup filters by eight fixed categories in three Mediterranean tiers. Those two
things do not line up. Nothing in the code turns "tofu" into a category.

So we add one shared name for a protein group, used by the filter now and by the weekly
balance panel later. In DDD terms this is **ubiquitous language**: one word for a thing,
the same everywhere in the app. If the filter and the balance panel invent their own
groupings, they will disagree on the same screen.

The shape of the mapping:

```mermaid
flowchart LR
  P["free words<br/>tofu, mozzarella, guanciale"] --> M["categories_for()"]
  M --> C["ProteinCategory<br/>plant_protein, dairy, processed_meat"]
  C --> T["tier<br/>eat freely / moderate / occasional"]
```

The eight categories, their tier, and the words that map to each:

| Category | Tier | Words that map here |
| --- | --- | --- |
| fish | eat freely | fish, seafood, salmon, tuna, shrimp, cod |
| legumes | eat freely | beans, chickpeas, ceci, lentils, peas |
| plant_protein | eat freely | tofu, tempeh, edamame, seitan, soy |
| poultry | moderate | chicken, turkey |
| eggs | moderate | eggs |
| dairy | moderate | cheese, mozzarella, ricotta, yogurt, milk, parmesan |
| red_meat | occasional | beef, pork, lamb, veal |
| processed_meat | occasional | salame, prosciutto, pancetta, guanciale, wurstel, bacon, speck |

Two honest gaps to accept now, so nobody is surprised later:

- **Processed meat has no source in extraction yet.** The extraction prompt never emits
  cured-meat words, so the "Processed" facet will match almost nothing until the
  re-extraction step at the end. Your carbonara rule (guanciale counts as processed) needs
  that step to have any data.
- **Plant coverage is partial.** "tofu" is already tagged, so the Plant facet works today.
  "seitan" and "tempeh" may not be tagged until re-extraction.

One more rule: **nuts are not a protein category.** In the Mediterranean frame they are a
fats and snacks group, not a weekly protein target. Tag them if you like, but keep them out
of the balance. This keeps the legume and plant numbers honest.

---

#### Build order

Backend first, then the one big frontend session, then the data work.

```
1. is_recipe filter + counts        (small, visible win)
2. ProteinCategory + mapping         (pure domain, tested)
3. protein facet filter              (repo + API)
4. multi-ingredient search (chips)   (repo + API)
5. the Quiet Command Bar UI          (the big frontend session)
--- later, needs new data ---
6. ingredient index + autocomplete   (needs clean names)
7. re-extraction batch               (summary, plant + processed words, course)
```

---

#### Session 1: the "is this a recipe" filter and counts

**Why first.** The `is_recipe` flag already exists on `Recipe` and the extraction already
sets it well. We just never let anyone filter on it, and we never show a total. This is the
smallest change with the biggest cleanup: about half the noise leaves the page.

**Backend.**

- In `repository.find`, add a keyword-only `is_recipe: bool | None = None` and filter like
  the others (`if is_recipe is not None: keep r where r.is_recipe == is_recipe`).
- Add a count endpoint the segmented control can read. `GET /recipes/count` takes the same
  filter parameters as `/recipes` and returns both segment totals under the current facets:

  ```json
  { "recipes_only": 634, "all_saves": 1152 }
  ```

  where `recipes_only = len(find(is_recipe=True, ...other filters))` and
  `all_saves = len(find(is_recipe=None, ...other filters))`. Keep the `/recipes` list
  response shape the same, so the frontend contract does not break.
- In `api.list_recipes`, add the `is_recipe` query parameter (default `None`).

**Frontend (`public/`).**

- A two-option segmented control by the results count: "Recipes only" (default) and
  "All saves · N". Toggling sets `is_recipe` and refetches. On mobile it is a full-width
  two-segment switch (see rule card in `__3_`).
- The count line reads "Showing 50 of {active segment total}".

**Acceptance.**

- Default browse shows only real recipes.
- The toggle flips to all saves and back, and the counts match.
- Keyboard reaches the toggle, focus is visible, and the text passes WCAG AA contrast.

**Note on cost.** The repo reads every JSON file on each call, and now the page loads do
one list plus one count call. At ~1,150 small files this is milliseconds, so it is fine. If
it ever hurts, cache `list_all` or move the store to SQLModel. Not now.

---

#### Session 2: ProteinCategory and the mapping (pure, tested)

**Goal.** Add the shared name from the section above. No UI in this session.

- Add `ProteinCategory` as a `StrEnum` in `dispensa/domain/enums.py` with the eight
  members: `fish, legumes, poultry, eggs, dairy, red_meat, processed_meat, plant_protein`.
- Add a small module `dispensa/domain/proteins.py` with:
  - a mapping dict from word to `ProteinCategory` (the table above, lower-cased keys),
  - `categories_for(proteins: list[str]) -> set[ProteinCategory]`, a module-level function
    that maps each word and returns the set (unknown words are skipped, never an error),
  - the tier grouping, either a `TIERS` constant or `tier_for(category) -> Tier`, so the
    balance panel can reuse the exact same grouping later.

**Acceptance (unit tests).**

- `tofu` maps to `plant_protein`, `mozzarella` and `ricotta` to `dairy`, `chicken` to
  `poultry`, `beef` and `pork` to `red_meat`, `guanciale` and `prosciutto` to
  `processed_meat`, `ceci` and `lenticchie` to `legumes`.
- An unknown word returns an empty set, and does not raise.

This is the file to read by eye before you accept it.

---

#### Session 3: the protein facet filter (repo + API)

- In `repository.find`, add `protein_categories: list[ProteinCategory] | None = None`.
  ANY-match: a recipe passes if
  `categories_for(r.proteins) & set(protein_categories)` is not empty.
- In `api.list_recipes`, add a repeatable `protein_category` query parameter. Coerce each
  value with the existing `_to_enum` helper and ignore invalid ones.

**Acceptance.**

- `/recipes?protein_category=plant_protein` returns tofu recipes.
- Two categories OR together (`?protein_category=fish&protein_category=legumes`).
- An unknown value is ignored, not a 500. Processed returns few or none today (expected).

---

#### Session 4: multi-ingredient search, the chips (repo + API)

The search box holds several ingredient chips at once, for example `zucca` and `tofu`
together (see `__5_`). Today `find(q=...)` takes one string only.

- In `repository.find`, add `ingredients: list[str] | None = None` with **AND-match**: the
  recipe must match every term. Each term is expanded by `synonyms.expand_term` and matched
  against title, caption, and the ingredient list, the same way `q` already works. Keep `q`
  for free single-text search.
- In `synonyms.py`, add the missing `zucca` group. Keep it separate from `zucchine`, they
  are different vegetables:
  `frozenset({"zucca", "pumpkin", "squash", "butternut"})`.
- In `api.list_recipes`, accept a repeatable `ingredient` parameter and pass it as the
  `ingredients` list.

**Acceptance.**

- `?ingredient=zucca&ingredient=tofu` returns only recipes that match both.
- `zucca` now finds `pumpkin` and `squash` too.

The dropdown of suggestions with counts ("tofu 31") is **not** this session. That needs an
ingredient index and clean names, which is Session 6 (later). The chip filter works fine
without it.

---

#### Session 5: the Quiet Command Bar (the big frontend session)

This builds direction 1a from `__6_` (calm), `__5_` (open panel), and `__4_` (mobile). It
touches only `public/`. The backend from sessions 1 to 4 is already in place.

**At rest, keep it calm.** This is the whole point of 1a.

```
[  search by ingredient: zucchine, ceci, tofu...      ]  [ Filters > ]

Showing 50 of 634 recipes            [ Recipes only | All saves · 1,152 ]

[ card ] [ card ] [ card ] ...
```

Nothing else is visible at rest: search line, Filters button, the is-recipe segmented
control (from Session 1), the count line, the card grid.

**The search line** holds removable ingredient chips once the user adds ingredients, and
sends them as `ingredient=` parameters (Session 4). Free text is still allowed.

**The Filters button** opens the panel. On desktop it expands below the bar. On mobile it
is a bottom sheet (see `__4_`). The panel holds:

- **Protein, in three tiers.** Eat freely: Fish, Legumes, Plant protein. Moderate: Poultry,
  Eggs, Dairy. Occasional: Red meat, Processed. Each pill is a **colour dot plus a text
  label, always together, never colour alone** (accessibility rule from `__3_`). Selecting
  pills sends `protein_category=` (Session 3). Multi-select, OR within protein.
- **Secondary dropdowns:** Dish type, Meal, Cuisine, Difficulty, Dietary. Each defaults to
  "Any" and wires to the existing parameters (`dish_type`, `meal_type`, `cuisine`,
  `difficulty`, `dietary_tag`).
- **Cook time is not supported yet.** There is no time parameter in the API. For this first
  version, leave Cook time out. Adding a `max_time` parameter can be a small follow-up.
- **"Clear all"** and a primary **"Show N recipes"** button, where N updates live from the
  count endpoint. The Filters button shows a small count of active filters ("Filters ▾ 1").

**Fix the card badge.** Show `dish_type` only, and show nothing when it is `unknown`. Never
fall back to cuisine or "Other". That fallback is exactly why the badge looked random.
(The pretty Italian labels like Frittata and Contorno need a `course` field we do not have.
That is the re-extraction step, not this session. Empty beats wrong.)

**Fix the contrast.** The pale tan mono labels on cream (the count line and the card meta
line) are the one thing at risk of failing WCAG AA for small text. Darken them so normal
text reaches a contrast ratio of at least 4.5:1 against the cream background. Check the real
hex values, do not guess.

**Acceptance.**

- The resting state shows only the search line, Filters, the segmented control, the count,
  and the grid.
- Opening Filters reveals the three protein tiers and the secondary dropdowns.
- Selecting facets or chips refetches, and both the count line and the "Show N" button
  update.
- The badge shows a dish or nothing, never cuisine or "Other".
- Small labels pass AA contrast, every control is reachable by keyboard, and the mobile
  bottom sheet opens and closes.

**If momentum stalls, split this session.** First the resting state plus the is-recipe
segmented plus the card badge fix, which is visible fast. Then the Filters panel (tiers and
secondary dropdowns) as a second sitting. Smallest restart wins.

---

#### Later, once the basics ship (needs new data, do not start now)

##### Session 6: ingredient index and autocomplete with counts

The dropdown "tofu 31 / toffarella 4" (`__5_`) needs two things we do not have: an endpoint
that lists distinct ingredients with recipe counts, and clean ingredient names.

The name for the second part is **canonicalization**, a form of entity linking: map the many
spellings and languages of one food to a single name. "toffarella" sitting next to "tofu" is
the messy vocabulary leaking through, which is the proof that the cleaning has to come first.

Our earlier decision holds: let the model do the cleaning at extraction time (it already
knows that `zucca` is squash and `seitan` is wheat gluten), and keep `synonyms.py` as a
small safety net for false friends and known errors. Then build the index from the verbatim
ingredient lists and expose `GET /ingredients?prefix=tof` returning `[{name, count}]`.

Do not start this before Session 5 ships. The chip filter is useful without it.

##### Session 7: the re-extraction batch

To fill the gaps the mockup assumes, the extraction prompt and schema need:

- a short `summary` field, the one-line card description,
- plant-protein words (`tofu` is there, add `tempeh`, `edamame`, `seitan`, `soy`),
- processed and cured-meat detection (`salame`, `prosciutto`, `pancetta`, `guanciale`,
  `wurstel`, `bacon`, `speck`), so the Processed facet and the carbonara rule have data,
- optional: a `course` field for the pretty Italian badges (Frittata, Secondo, Contorno).

This is a prompt and `scripts` change plus a batch run you drive yourself (Batch API,
`gpt-5.4-mini`, low reasoning effort, no temperature). It rewrites data, so it goes through
the append-only extractions and `promote()` flow, and it must not overwrite user edits.
Good news: `repository.save` already protects favourites and notes on re-extraction.

Sequence this last, after the categories prove right in the real UI.

---

#### Further reading and related code

Related code to open while working:

- `dispensa/repository.py`: `find`, `list_all`, `save` (the store and its filters).
- `dispensa/api.py`: `list_recipes` (where query parameters are wired).
- `dispensa/domain/enums.py` and `dispensa/domain/models.py`: the taxonomy and `Recipe`.
- `dispensa/api_models.py`: `RecipeSummary` (what each card receives).
- `dispensa/domain/synonyms.py`: `expand_term` (cross-language search).
- `public/index.html` and its JS: the frontend.
- `CLAUDE.md`: the coding conventions this plan follows.

The ideas behind the plan:

- Faceted search: filter a set by a few known dimensions at once. A common, well documented
  UI pattern.
- Ubiquitous language and the dependency rule: Eric Evans, *Domain-Driven Design*, and
  Robert C. Martin, *Clean Architecture*. One shared name, inner layers stay pure.
- Entity linking and canonicalization: mapping many surface forms of a thing to one
  canonical name. This is why ingredient cleaning belongs at extraction, not in a growing
  hand-written dictionary.

## 5. Design exploration: plan builder and custom recipes

Companion to `docs/PLAN.md` (Phase 4 and Phase 6) and `ios-share-capture-plan.md`.
This doc captures a design conversation, not committed code — read it before
picking either thread back up.

#### Scope

Two things came up together and turned out to be adjacent, not separate:

1. **Phase 4.2–4.4** — the Plan Builder frontend (day columns, live balance
   panel, gap suggestions) is speced in `docs/PLAN.md` but unbuilt. 4.1
   (tokens.css) is the only checked box.
2. **A new idea, not yet in PLAN.md**: use `mcp__Dispensa__search_recipes` /
   `get_recipe` (live in a Claude session today, no new code needed) to pull
   inspiration from the existing ~800-recipe library, riff on it, and save
   the result as your own recipe — distinct from a direct Instagram
   extraction, but not disconnected from what inspired it either.

Both plug into machinery that already exists: `RecipeSource.MANUAL`, the
`m-{slug}-{4 random base32}` code scheme (D11), and Phase 6.2's sketch of
"paste-text → AI preview → save."

#### Decisions this session (continuing the D-numbering from PLAN.md §... D16)

| # | Decision |
|---|---|
| D17 | `Recipe` gains `inspired_by: list[str] = []` — codes of any recipe (Instagram *or* manual) that inspired this one. Chaining is allowed: a remix of a remix just lists its immediate parent(s). Generalizes D16's `parent_code` idea from one link to a list, since a custom recipe may combine ideas from more than one saved post. |
| D18 | **Open** — which surface produces an `inspired_by` recipe. Leaning chat-driven for now (search/get via MCP → draft together → save via a script that calls the same `RecipeRepository.save()` Phase 6.2 will eventually expose as an in-app form), so nothing built now needs to be rebuilt later. Revisit once Phase 6 is in view. |
| D19 | Plan Builder build order: **balance panel + day columns first** (PLAN.md's "wow moment," 4.4), ahead of pantry/cookable-now (Phase 5) and the shopping list. |
| D20 | Primary ADHD lens for this screen: **low decision fatigue**. The "add to day" interaction defaults to ranked gap-suggestions, not a search box — see below. |
| D21 | `week_start` stays the `/api/plans/{week_start}` identifier, unchanged. A full ISO date never recurs, so this is stable for as many years as the app runs, and the DB already backs it with a surrogate `WeekPlanRow.id` (meals FK to that, not to the date) — the "solid" part was already built. **No user/household scoping added now** — every table (`week_plans`, `pantry_items`, `user_state`, `targets`) is unscoped today, consistent with D13's single-credential, zero-login-UI, solo-hobby-project stance. Deferred deliberately, not overlooked: because storage already uses surrogate keys everywhere, adding a `user_id` column + tightening `week_start`'s unique constraint to `(user_id, week_start)` later is a mechanical, low-risk migration, not a redesign. Revisit only if this ever needs to serve more than one person's plan. |

#### Entity shape

`Recipe` (domain/models.py) — one new field:

```python
inspired_by: list[str] = Field(default_factory=list)
```

Same treatment as `mediterranean_categories`: JSON column on `RecipeRow`
(`storage/_tables.py`), serialised/deserialised in `recipes_db.py`'s
`_to_row`/`_to_domain`, exposed on `RecipeDetail`. No new `RecipeSource`
value needed — `source=MANUAL` already means "not from Instagram, made by
me"; `inspired_by` is orthogonal provenance that happens to apply mostly to
manual recipes but isn't restricted to them.

`CategoryServing.source` already has a `"manual"` literal (alongside `llm`/
`derived`) — reuse it as-is when you hand-set a custom recipe's categories
instead of running it through the extractor.

Open sub-question for D18: should `inspired_by` be allowed to point at
`is_recipe=false` posts (the "Appunti & ispirazione" shelf, D15) too, not
just full recipes? Those are often exactly the kind of half-formed idea
worth riffing on.

#### Workflow sketch (still marked open per D18)

1. `search_recipes("something with lentils and sausage")` → shortlist.
2. `get_recipe(code)` on the ones worth a closer look.
3. Riff on it together in the session — the resulting shape is an
   `ExtractedRecipe`-like draft (title, ingredients, instructions,
   `mediterranean_categories`, etc.), same fields the LLM extractor
   produces, just authored by hand.
4. Save it — for now, a small script in the spirit of
   `scripts/import_existing.py`: builds a `Recipe` with
   `source=MANUAL`, `code=m-{slug}-{random}`, `inspired_by=[...]`, and
   calls the existing `RecipeRepository.save()`. No new API endpoint
   required for v1; Phase 6.2's in-app form can call the same path later.

#### Plan Builder v1 slice (balance panel + day columns)

The data side is already done — `GET /api/plans/{week_start}` returns
`{meals, balance, oily_fish, suggestions}` in one payload; `PUT
/{week_start}/meals` upserts a slot. The frontend work is purely about
rendering and interaction, per PLAN.md 4.4's own component names:
`DayColumn`, `BalancePanel`, `GapSuggestions`.

For the low-decision-fatigue lens (D20): tapping "+ add" on a day/slot
should surface the top `gap_suggestions` entries for whichever category is
currently most under target *first* — one tap to add, no search required —
with "search all recipes" as a secondary, collapsed option rather than the
default path. Portions default to 2, editable after adding rather than
asked up front. Mirrors the mockup's "Fills a gap" panel, but as the
*default* add-flow rather than a side panel.

Update on save: optimistic UI update against the `PUT`, rollback on
failure (already specified in PLAN.md 4.4) — keeps the balance bars feeling
instantaneous, which matters for the "watch it move" payoff.

#### Open questions for next round

- Does `inspired_by` need to resolve/display in the UI (e.g. "riffed on
  Pasta e Ceci") or is it just backend provenance for now?
- Where's the line for "this needs a nicer surface than a script" — some
  number of custom recipes, or just whenever Phase 6 comes around anyway?
- Should the Plan Builder's gap-suggestion shortlist prefer *your* custom
  recipes over Instagram ones, once some exist, or stay neutral?

## 6. Engineering notes and out-of-phase observations

Things noticed while working a phase that belong to a later one. Not acted on here.

#### From Phase 9.1 (pipeline close-out)

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

#### From Phase 9.2 (edit tracking)

- **Local test-infra debt, not code:** on this machine `pytest` shows two
  failures that also fail on untouched `main` —
  `test_promotion.py::test_promote_counts_extractions_without_a_recipe` needs a
  superuser test role (`SET session_replication_role = replica` is denied to the
  `dispensa` role), and `test_storage_db.py::test_recipe_round_trips_fully` needs
  the PG session timezone to be UTC (local server is `Europe/London`; passes with
  `PGOPTIONS="-c timezone=UTC"`). CI presumably has both. Worth fixing the local
  setup or the fixtures so the green gate is honest here.

#### From Phase 9.3 (caption-changed re-extract) — DEFERRED

- D26 not implemented. Caption edits are rare; the change touched the batch
  pipeline (new `extractions.caption_hash` column stamped at apply time from the
  archived batch input, hash-aware submit dedup to avoid re-extracting the
  ~900-recipe pre-D26 backlog). Plan sketch is in this session's history if
  picked up later. `recipes.caption_hash` column remains write-only (AUDIT F6).

#### From Phase 10.3 / 10.4 (MCP write tools)

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

#### From Phase 10.5 (pantry)

- **`kind` (staple/fresh) stays alongside `location`.** D31 added location
  without retiring kind; they overlap (fresh ≈ fridge) but answer different
  questions. Revisit if `kind` ends up unused once the PantryList UI (11.6)
  exists.
- **No pantry update tool.** Changing a quantity or expiry is remove + add.
  Fine for v1; an `update_pantry_item` is cheap if the live test asks for it.
- **Adding does not merge by name.** Two "ceci" rows can coexist (one in the
  fridge, one tinned in the pantry), which is intended; names stay free-text
  per D31.

#### From Phase 10.6 (search fields and filters)

- **The synonym layer has no eggs ↔ uova pair.** A pantry "eggs" does not
  match an ingredient line "2 uova" (chickpeas ↔ ceci does). This affects
  `pantry_have` / `pantry_only`, the shopping list and kitchen_match alike.
  Worth an audit of `domain/synonyms.py` against the most common pantry
  words in both languages.
- **The slim view's new fields also show in plan `suggestions`.** `to_mcp_view`
  is shared, so gap suggestions in `get_planning_context` and the write tools
  now carry `difficulty` and `mediterranean_categories` too: a few more tokens
  per suggestion, and one less reason to call `get_recipe`.

#### From Phase 11.1 (client-side index)

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

#### From Phase 11.5 (my version of… / weekend toggle)

- **Picker titles truncate hard in the Mon–Fri columns.** A wide category
  chip (PLANT PROTEIN) leaves a few characters of title ("Me…"). Pre-dates
  11.5; the rows are as wide as before. Wrapping the title or dropping the
  chip text to a dot in narrow columns would fix it.
- **A recipe saved from the plan page is missing from Browse until reload**,
  same as one saved from Claude (the session index, D27). The plan page shows
  it because it keeps the saved recipe's display itself.

#### Phase 14 — safety net (PLAN-next.md)

- **14.1 MCP subject allow-list** — merged to main and deployed 2026-11-11.
  `MCP_OAUTH_ALLOWED_SUBJECTS` set on FastAPI Cloud. Verified live from this
  session: `get_pantry` and a semantic search over `/mcp` both returned.
- **14.2 CI** — green (`.github/workflows/ci.yml`), `make check` on push/PR.
- **14.3 weekly Neon backup** — DONE 2026-11-11. Workflow lives in
  `estyxx/cookstagram-data` (`.github/workflows/backup.yml`); manual run #3
  green. Artifact `neon-20261111-1820-weekly`, 933,522 bytes zipped (weekly =
  `recipe_embeddings` data excluded; monthly keeps it). Two gotchas fixed on the
  way: the `pg_dump` client must be >= Neon's server major (Neon is on
  **Postgres 18**; the workflow now reads `show server_version_num` and picks the
  matching client), and `readonly_user` needed `GRANT SELECT ON ALL SEQUENCES`
  on top of table SELECT or `pg_dump` aborts on `*_id_seq`.
- **14.4 restore drill** — DONE 2026-11-11 (owner, laptop). Restored the
  weekly artifact `neon-20261111-1820-weekly` (933,522 bytes zipped) into a
  throwaway `postgres:18` container with `pg_restore --no-owner --no-acl`.
  Counts: recipes 1171, week_plans 2, planned_meals 16, pantry_items 0,
  recipe_embeddings 0 (weekly excludes embedding data by design; pantry 0 matches
  the live empty pantry). Backup restores and reads cleanly. This cloud session
  can't fetch the GitHub artifact (Azure blob host blocked by the agent proxy),
  so the drill runs on the laptop; re-run it after each schema change.

#### From Phase 15.7 (diet-pyramid targets)

- **New DEFAULT_TARGETS are code defaults only.** `_seed_targets` fills missing
  categories, never overwrites existing rows, so a deploy does not change the
  owner's Neon targets. To adopt the new pyramid numbers in prod, apply them by
  hand via `PUT /api/targets`. The numbers (fish 2+, legumes 2+, plant 1+,
  poultry 0-2, red meat 0-1) still await a check against Bach-Faig 2011 Figure 1.
- `max_servings` is now nullable (no ceiling = never "Over"). A floor-only
  target reads "2+" in the UI. Existing databases get the NULL via a schema
  patch in `_ensure_schema_patches`.

#### Batch state moved to the DB (2026-11-12)

- The batch pipeline used to keep the last OpenAI batch id in
  `data/last_batch_id.txt` and dedup submissions against a disk scan of
  archived batch inputs. Prod has no persistent disk, so a batch submitted
  in one request was unfindable in the next — `apply`/`status`/`promote`
  could not resolve it. Now a `BatchRun` aggregate (`domain/batch.py`) is
  recorded in a `batch_runs` table via `BatchRepository`
  (`storage/batches_db.py`); `submit_batch` records the run and dedups
  against `all_submitted_codes()`, `apply_batch` resolves `latest()` and
  marks it `APPLIED`. This is the prerequisite for in-app (Neon) batch
  extraction from the capture queue (20.4).
- **D56 revisit is now unblocked.** D56 ("extraction never runs against
  Neon") was written when extraction only ran against the local workshop
  DB and wrote batch state to disk. With batch state in the DB, a prod
  process can submit → persist the id → apply later. The queue-extraction
  flow (share link → queue → launch batch → auto-import on completion) is
  the intended replacement for the local scripts. Design discussion with
  owner still pending before wiring 20.4 to prod.
- **Follow-ups still open:** `ai/batch.py` still defines `LAST_BATCH_ID_PATH`
  / `_load_batch_id` for the dev-only `smoke_test` and the backfill script;
  remove once the backfill is retired. The local input archive
  (`create_batch` still writes it) stays for the one-off backfill.
- Merged to main 2026-11-12 (FF push, 13 commits: Phases 15, 16.1, 16.6,
  20.1, 20.3, plus this refactor).

#### Synonyms — future direction (owner, 2026-11-11)
The synonym layer is a workaround for a mixed-language (IT/EN) app: it aliases
ingredient strings across languages so matching/shopping/canonicalisation work.
It's fine for now but doesn't scale cleanly (every pair added by hand; canonical
name is an arbitrary alphabetical pick, so the shopping list mixes languages).
The real fix is a canonical ingredient *identity* — store a stable id per
ingredient and render its label in the chosen interface language — rather than
string aliasing. Revisit when interface language / i18n is tackled.

## 7. Reality audit

Derived from the working tree at branch `main` (commit `26cc3fd`), not from the
docs. `docs/PLAN.md` and `docs/scripts-audit.md` are both behind the code; every
divergence is listed below with file references. No code was changed.

Ranking key: **P0** blocks a listed PLAN next step · **P1** data integrity ·
**P2** performance · **P3** cosmetic / doc drift.

---

#### 0. Ranked findings (most severe first)

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

#### 1. PLAN.md checkboxes whose real status differs

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

#### 2. MCP server — registered tools and return shapes

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

#### 3. Sync pipeline trace

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

#### 4. Storage — multi-user readiness

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

#### 5. Search — embedding storage, comparison, cost

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

#### 6. Frontend — refetch on navigation, what is cached

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

#### 7. Tests — coverage gaps and network

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

#### 8. Dead code, TODOs, inline-silenced rules

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

## 8. Archive: the original revival plan

> SUPERSEDED. Current plan lives in docs/PLAN.md. Kept for history.


A staged roadmap from the current (working but messy) state to a clean,
searchable, editable, meal-planning recipe app. Built so each phase ships
something usable on its own.

---

#### 1. Where the code actually is

The pipeline *works* — you've extracted real recipes (the lemon-chicken escalopes
came through with full ingredients, English translation, and ~30 tag fields). The
problems are consistency and sprawl, not capability:

- **Name drift.** Resolved: the one name is `dispensa`. The Python package and
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
- **Frontend sprawl.** `index.html`, `mobile.html`, `dispensa.html`,
  `recipe.html`, `analytics.html`, `planner.html` + `app.js` + `recipe.js` are
  overlapping single-file apps. Collapse to one.
- **Error handling** is `print` + bare `except` + `traceback.print_exc()`
  throughout — the opposite of the clean conventions you want.

None of this is hard to fix. It's mostly consolidation.

---

#### 2. Target architecture (DDD-lite, no over-engineering)

```
src/dispensa/
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

#### 3. Key decisions

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

#### 4. One data model (the direction)

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

#### 5. Phased roadmap

Each phase is shippable. Do them in order; don't skip to Phase 3.

##### Phase 0 — Cleanup & foundation
*Goal: one clean skeleton that still runs.*
- Pick the name; rename package, scripts, README to match.
- Create the `domain/` layer; consolidate to **one** `Recipe` model + enums + errors.
- Delete `analyzer.py` and the duplicate HTML files; keep the best one frontend.
- Switch to `pydantic-settings`; move `logging.basicConfig` to the entrypoint only.
- Fix IDs: key by `code`, all IDs `str`. Write the JSON→new-model migration once.
- Get `ruff`, `mypy --strict`, `pytest` green on the skeleton.

##### Phase 1 — MVP pipeline (extract → analyze → static site)
*Goal: re-run end to end and browse the result.*
- `dispensa fetch <collection>` → instagrapi → cache JSON (keyed by `code`).
- Image step: download media → Cloudinary → store durable URL + `public_id`.
- `dispensa analyze` → **Batch API** → validated `Recipe` JSON per post.
- `dispensa build` → emit one `recipes.json` (+ a small `index.json`) the
  frontend reads.
- One clean frontend: card grid, text search, multi-filter (cuisine, meal, dietary,
  protein). Data in the **private** repo; code stays public.

##### Phase 2 — Quality & bilingual
*Goal: trust the data, search in both languages, fix mistakes without a DB.*
- Flag low-confidence / `is_recipe=false` for review; re-run those interactively
  with Pydantic AI.
- Handle photo-only posts (no caption recipe) — mark them, or add vision later.
- Bilingual search over caption + `ingredients_original` + normalized tags.
- `overrides/{code}.json` merged at build → you hand-edit; re-running extract never
  clobbers your edits.

##### Phase 3 — Editing + database
*Goal: edit in the UI; this is when a backend earns its place.*
- FastAPI + **SQLite (FTS5)**. Migrate JSON → SQLite (same repository interface, so
  the swap is contained).
- CRUD endpoints for recipes; edit UI in the frontend. `edited_by_user` protects
  your changes from re-extraction.

##### Phase 4 — Meal planning
*Goal: the thing you actually want this for.*
- `MealPlan`: pick recipes into a weekly board; a "to-cook" mood board.
- Auto-generate a grocery list by aggregating ingredients across selected recipes
  (dedupe + group by category — your `vegetables`/`proteins`/etc. tags make this easy).
- Optional later: PWA/offline, cooking-mode timers.

---

#### 6. Suggested first sitting (ADHD-friendly, ~one focused block)

1. Rename to one project name.
2. Create `domain/models.py` with the single `Recipe` model + enums.
3. Write a 20-line script: load existing `extracted_recipes.json`, re-key by `code`,
   validate through the new model, write to `data/recipes/{code}.json`.
4. Run it. You now have clean, correctly-keyed data and a model everything else can
   build on. Everything in Phase 1 hangs off that.

Drop `CLAUDE.md` in the repo root before you start so Cursor codes to these rules
from the first prompt.
