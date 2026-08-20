# Dispensa (foodiegram)

A personal Mediterranean-diet recipe library + weekly meal planner. Ingests Instagram
saves, extracts structured recipe data from the Instagram's caption with OpenAI, exposes it to Claude via an MCP
server for meal planning and serves a browsable site for searching recipes and planning a week of meals. Solo hobby project, personal use, ADHD-friendly by design.


## Architecture — layered, enforced by import-linter

```
routers/api → app → storage | ai | images | instagram → domain
```

- `domain/` — pure models, enums, business rules. Imports nothing above it. **Domain is pure.** Files in `domain/` do no I/O — no network, no disk, no env, no SDK clients. If you're importing `openai` or `instagrapi` there, stop.
- `app/` — use-cases as module-level functions. The ONLY layer that may combine
  siblings (e.g. ai + storage). Composition point.
- `storage/` — persistence. SQLModel row classes are PRIVATE here and never cross the
  boundary; repositories return/accept domain objects.
- `ai/` — OpenAI (extraction, embeddings). `images/` — Cloudinary adapter.
  `instagram/` — scrape/cache (see "Instagram" below).
- Respect the boundaries. If a change seems to need reaching past a layer, STOP and ask.

## Green gate — must pass before any change is "done"

```
uv run ruff check --fix .
uv run ruff format .
uv run mypy src
uv run pytest -q
uv run lint-imports
```

Run it, fix what breaks, re-run until clean. Don't skip a check. (Also available as `/green`.)

## Python conventions

- Target Python 3.14. **Never** `from __future__ import annotations`; put annotation-only
  imports under `if TYPE_CHECKING:`.

- Keyword-only arguments after the first parameter. Explicit return annotations on every function. Use-cases are module-level functions, not service classes.

- **No `**kwargs` in our own code.** Every function signature is explicit and typed. (LLM/SDK boundary objects are the only exception, and even there, unpack into
   named fields immediately.) Type with `object` instead of `Any`.

- **Type everything.** Code must pass `mypy --strict`. No bare `Any` unless genuinely unavoidable, and then with a `# reason:` comment.

- **Never `print`.** Use the module `logger`. Never `traceback.print_exc()`.

- **No bare `except Exception: pass`.** Catch the narrowest thing, log it, and either re-raise a typed error or return a typed result. See "Errors" below.

- `StrEnum` with an `UNKNOWN` fallback member is the enum convention.

- OpenAI: pinned model snapshots; `max_completion_tokens` not `max_tokens`; no `temperature` on reasoning-model requests.

- **Don't add a dependency without asking.** We already have what we need.

## Working principles

- **Empty beats wrong.** Show nothing rather than a fabricated or corrupted value. A missing field is `None`/`[]`/`""`, never a placeholder or a guess.
- **STOP and report — no silent workaround.** If the real tree contradicts an instruction, or an assumption turns out false, stop and surface it. Don't paper over.
- **Verify against real data.** Confirm hypotheses with a SQL query or probe script before acting on them. Don't infer schema/behaviour from filenames.
- **Domain logic lives in the app, not in prompts.** Claude proposes; the app validates. The Mediterranean balance engine, weekly targets, and weighting rules are the source
  of truth and are never reimplemented in an LLM prompt.
- **Data ops are additive and idempotent.** `db dump` before any write. Print the target host/DB; refuse a prod host (`neon.tech`/`neon.build`) unless `--yes`.


## Data & environments

- **Local Postgres is the source of truth.** Neon is downstream (prod). Extraction and batch processing run locally, then promote to Neon deliberately.

- `extractions` is append-only (reversible history). `promote()` merges extractions → `recipes` and NEVER overwrites a field listed in `edited_fields` (user-owned).


## Domain facts

- **Language split:** `title`, `ingredients`, `instructions` stay VERBATIM in the caption's original language (mostly Italian). All tag/classification fields use canonical English. A synonym layer handles cross-language search.
- **Mediterranean categories (8, first-class):** fish, legumes, poultry, eggs, dairy, red_meat, processed_meat, **plant_protein**. tofu/tempeh/edamame/seitan → plant_protein (NOT legumes; legumes are whole pulses). Cured meats → processed_meat at full weight.
- **Two hashes drive change-detection:**
  - `recipes.caption_hash` = sha256(normalized caption) → "caption changed?" → re-extract.
  - `recipe_embeddings.embedding_source_hash` = sha256(`recipe_document(recipe)`) →
    "embedded document changed?" → re-embed. Moves on re-extraction even when the caption
    is identical. These are different sources; don't collapse them.
- **RAG:** semantic search via `RecipeRepository.find_similar` — JSON embeddings + Python
  cosine (pgvector deferred until ~10k rows). Returns `list[tuple[Recipe, float]]`; the
  score rides to the MCP/UI boundary. **No absolute similarity threshold** — correct
  cross-language hits land near 0.50; any fixed cutoff silently drops them.
- **Extraction prompt:** `ai/prompts/extract_recipe_details.txt`. `PROMPT_VERSION` lives
  in `ai/batch.py`. Bump it when the prompt changes so re-extracted rows are distinguishable.


## The `sync` workflow (Stage B — offline, idempotent)

`sync` reconciles a downloaded `food.json` against the DB, doing only needed work:
`dedupe-links · ingest · extract · status · apply · promote · embed --changed · all`.
- `ingest`: per shortcode, independent flags — new? / caption changed? / image missing or
  broken? — acting via the app use-cases and the `images/` Cloudinary adapter.
- `extract`: submits an OpenAI batch (async — returns immediately, batch completes later).
- `status`: polls the OpenAI batch (`--batch <id>`, default: last submitted) and prints
  its completion counts. Not required — just a convenience while waiting.
- `apply`: once the batch is `completed`, downloads its output and appends
  `extractions` rows (kind=`batch`). Never touches `recipes`. **Required before
  `promote`** — `promote` only ever reads from `extractions`, so skipping `apply`
  after a batch finishes leaves `promote` with nothing to promote
  (`considered=0`).
- `embed --changed`: re-embed only stale (document_hash ≠ stored) or embedding-less rows.
- `all`: ingest → extract → promote → embed, in order, stop on first error. Does NOT
  scrape, dedupe, poll `status`, or `apply` — `extract` is async, so `all` cannot wait
  out a batch; run `status` / `apply` / `promote` by hand once the batch completes.


## Instagram — account risk, keep isolated

Stage A (getting saves) is the **IGbulkCollector browser extension → IGbulkDL → food.json**
path. The instagrapi login is flagged/frozen; do not casually script Instagram. `sync`
never touches Instagram — it reads a `food.json` that already exists.


## Don't

- Don't add pgvector yet (deferred until ~10k rows).
- Don't reimplement the balance engine or targets in a prompt.
- Don't let SQLModel rows leak out of `storage/`.
- Don't scrape Instagram from automation without explicit intent.


## Tooling

- **uv** for everything (`uv sync`, `uv run`, `uv add`). No `pip`, no `poetry`.
- **ruff** with `select = ["ALL"]` (current config). Don't silence a rule inline;
  if a rule is genuinely wrong for us, add it to `ignore` in `pyproject.toml` with
  a comment, repo-wide.
- **mypy** strict. **pytest** for tests. **pre-commit** runs ruff + import-linter on commit.
- Python **3.14+** (`requires-python = ">=3.14"`, ruff `target-version = "py314"`).

## Typing & style

- **Inputs at the top.** Module-level inputs, constants, and config go at the top of the file, above the functions and classes that use them.
- **Never** `from __future__ import annotations`. On Python 3.14 (PEP 649) lazy annotations are the default, so it is never needed; keep annotation-only imports under `if TYPE_CHECKING:`. (Supersedes the older 3.13-era "only when you need it" guidance that used to live here.)
- Modern syntax: `str | None`, `list[str]`, `X | Y`. Never `Optional`, `List`, `Union`.
- Line length 89 (ruff config). Let the formatter win; don't hand-wrap.
- Public functions and classes get a one-line docstring, imperative mood, ending with a period (PEP 257). **No module-level docstrings** (`D100`/`D104` are ignored). Never write a docstring or comment that just restates the code —
  comments explain *why*, not *what*.
- **No `# type: ignore`** — fix the root cause; if genuinely unavoidable, add a
  `# reason:`. No `assert x is not None` in non-test code when the type already
  rules out `None`; an `is not None` guard on a non-optional field is dead code that
  mypy will flag. No `hasattr()` duck-typing on typed objects — extend the type.
- Early returns over deep nesting. Extract a function that's doing two things.
  Prefer named constants / enum members over magic strings in conditions.

## Data modeling

We standardize on **Pydantic v2** because our data crosses three validation
boundaries (Instagram SDK, LLM JSON output, persisted files/API). Don't mix in
`attrs` — Pydantic gives us validation + JSON schema + immutability in one place.

- Entities and anything (de)serialized → **Pydantic `BaseModel`**.
- Immutability is the default: `model_config = ConfigDict(frozen=True)` unless a
  field genuinely needs to mutate in place (it usually doesn't — build a new copy).
- One model per concept. We do **not** keep two `Recipe` definitions around.
- Closed sets (meal type, difficulty) are `StrEnum`. Open, growing sets
  (ingredients, free tags) are `list[str]` — don't force them into enums.
- Prefer explicit constructors over `Model(**blob)`. If you must splat an external
  blob, validate it through the model (`Recipe.model_validate(blob)`), never
  `Recipe(**blob)`.
- **Typed objects over `dict[str, Any]`.** Pass Pydantic models around, not loose
  dicts; use dot-access (`recipe.title`), not `recipe["title"]`. A `TypedDict` is
  fine only for shapes that must stay dicts (raw JSON payloads, framework context).
- If you override `__eq__` to compare a subset of fields, keep `__hash__` consistent
  (hash fields ⊆ eq fields) and document why — Pydantic compares all fields by
  default.
- **Nullable storage column ≠ optional domain field.** If the read path always
  resolves a missing/`NULL` value to a default, absorb that at the storage boundary
  and expose a required, fully-typed field to the domain. Don't leak a pre-migration
  `T | None` upward.

## External data invariants (these have already bitten us)

- **Key recipes by Instagram `code` (the shortcode, e.g. `DJq4i8ysCL8`)**, not by
  `Media.id`. `Media.id` is `"{pk}_{userid}"` and produced corrupted keys like
  `36329647417694707168004905221`. The shortcode is stable, short, and gives the
  canonical URL `https://www.instagram.com/p/{code}/`.
- **All Instagram IDs are stored and handled as `str`.** They overflow JS number
  precision and round-trip badly through JSON as ints. `pk: str`, never `int`.
- **Preserve original language.** Store the caption verbatim. Search must work in
  both languages — never overwrite Italian content with English translations.
- Instagram media URLs **expire**. Capture the image at extraction time and store
  the durable (Cloudinary) URL. Never persist a raw cdninstagram URL as the
  source of truth.
- **Ingredient strings stay raw.** Store `"750g chicken breast"` as-is; do not
  destructure into `{quantity: 750, unit: "g", item: "chicken breast"}` in the DB.
  The scaling regex (`/(\d+\.?\d*)/`) handles numeric extraction at read time in
  both the JS frontend and the `/scale` API endpoint.

## Errors & logging

- One small exception hierarchy per area, e.g. `class FoodiegramError(Exception)`,
  then `InstagramFetchError`, `ExtractionError`, `StorageError`. Raise these, not
  bare `Exception`.
- Catch narrowly, log with `logger.exception("context: %s", value)`, then re-raise
  a typed error or return a typed failure. No silent swallowing.
- `logger = logging.getLogger(__name__)` per module. Configure logging once, at the
  CLI/app entrypoint — never `logging.basicConfig` inside library modules.

## Dates & times

- Call the clock (`now()`) **once, at the CLI/use-case edge**, and pass the value
  down. Never hide a clock call below that line: no `default_factory=now` on a
  domain field, no parameter that defaults to `None` and resolves to `now()` inside
  a domain function. Make `extracted_at` and similar required at the boundary.

## Package layout

The file map that accompanies the Architecture section above (same layering; DDD-lite,
not full DDD). Package: `foodiegram`. Module root: `src/foodiegram/`.

```
domain/               pure models, enums, errors + pure logic. No I/O. No SDKs.
  enums.py            StrEnum: MealType, DishType, CuisineType, Difficulty, Course, MedCategory…
  models.py           Recipe, ExtractedRecipe, Extraction, CategoryServing,
                      ExtractedCategoryServing, MappedRecipe, UserState (Pydantic, frozen)
  errors.py           FoodiegramError hierarchy
  editing.py          promote() + user-owned-field rules
  diffing.py          field-level diff between extraction payloads
  planning.py         WeekPlan, PlannedMeal, targets, balance math
  pantry.py shopping.py proteins.py synonyms.py   more pure logic
app/                  use-cases as module-level functions: extraction, promotion,
                      plan_week, export, import_json, diff_batch, review_categories…
storage/              SQLModel-backed repositories (see below). Rows never leave here.
ai/                   LLM extraction: batch.py (Batch API), repair.py (pydantic-ai),
                      prompts/*.txt.
images/               Cloudinary adapter: upload_thumbnail +
                      is_valid_image_ref (the missing-or-broken predicate).
instagram/            instagrapi adapter: _auth, extractor, cache_manager, collection.
                      Knows about Media; the Collection model lives here.
routers/              FastAPI routers: recipes, plans, pantry, targets, meta.
api.py                create_app() factory: wires the routers, Basic auth, gzip, CORS,
                      and serves the SPA. main() runs uvicorn.
api_auth.py           Basic auth middleware.
api_models.py         API-layer response models (RecipeSummary, RecipeDetail, etc.)
deps.py               builds the repositories from settings; injected into routers.
settings.py           pydantic-settings BaseSettings. Env prefix FOODIEGRAM_.
                      Never log the settings object itself.
```

`cli.py` exposes typer command groups over `app/` (`db` for local-DB maintenance,
`sync` for Stage-B ingestion); `scripts/*.py` are thin wrappers; `foodiegram.api:main`
runs the server.

Storage is **SQLModel** on Postgres everywhere (local working DB, a separate test DB,
and Neon in prod, via `DATABASE_URL` / `DATABASE_URL_TEST`; SQLite fully removed, the
cutover and Neon deploy done) behind hand-written
repositories, one per aggregate: `recipes_db.RecipeRepository`,
`extractions_db.ExtractionRepository` (append-only), `plans_db.PlanRepository`,
`pantry_db.PantryRepository`, `targets_db.TargetRepository`,
`user_state_db.UserStateRepository`. `storage/db.py` owns the engine/session and
`_tables.py` holds the SQLModel rows, which **never leave `storage/`** —
repositories accept and return domain models. `recipes_json.py` is legacy JSON,
kept for import/export only.

`RecipeRepository`'s interface is the stable API and must not change out from under
callers: `get`, `exists`, `list_all`, `save`, `delete`, `find`, plus the RAG methods
`find_similar`, `save_embedding`, `get_embedding`, and (read-only)
`embedding_source_hashes`. Callers import the repository, never the table classes.

The `/scale` endpoint is a **convenience** — it is not the source of truth for the
scaling widget. The browser JS (`extractNumber` / `scaleIngredient`) does the same
math client-side on already-loaded data. Never let the UI depend on a round-trip for
a calculation it can do locally.

No repository-of-repositories, no unit-of-work, no domain events, no generic
`BaseService`. If an abstraction has exactly one implementation and always will,
don't write the abstraction — write the function.

## Module conventions

- Private modules and helpers are `_underscore_prefixed`.
- Each package's public surface is re-exported in its `__init__.py`; import from the
  package, not from deep internal paths.
- A module that's getting past ~200 lines is a smell — split by responsibility.

## LLM / extraction conventions

- Prompts live in `ai/prompts/*.txt`, loaded at runtime. Never inline a big prompt
  in code.
- Output is **structured**: define the Pydantic output model and request strict
  JSON schema. Don't regex or hand-parse model prose.
- **Bulk first pass** (hundreds of posts): OpenAI **Batch API** (≈50% cheaper).
- **Interactive re-analysis / repairs** (one post, on demand): use **Pydantic AI**
  (we already depend on `pydantic-ai-slim`) so validation + retries are automatic.
- The pinned extraction model (`gpt-5.4-mini-…`) is a **reasoning** model and
  **rejects `temperature`** — never set it. Get determinism from low reasoning
  effort (`reasoning={"effort": "low"}`), not from a sampling temperature.

## Secrets

- `pydantic-settings` `BaseSettings`, loaded from `.env`. The settings object's
  `repr` must mask anything matching KEY/PASSWORD/SECRET/TOKEN (we already do this —
  keep it).
- `.env`, `cache/`, and `data/` are git-ignored. Recipe **data** lives in a separate
  private repo; **code** stays public. Never commit captions or credentials.

## Testing

- `pytest`. Unit tests do **no** network and **no** real disk outside `tmp_path`.
- Mock adapters via Protocols (define `InstagramClient`, `RecipeStore` protocols;
  pass fakes in tests). Don't monkeypatch the real SDK.
- Test the mapping/parsing logic (Media → domain, LLM JSON → Recipe) hardest —
  that's where the bugs live.
- Prefer a typed setup object over plain dicts in fixtures (a small frozen
  dataclass or Pydantic model, returned from a typed `pytest.fixture`). Don't leave
  fields on it that no test reads, and avoid importing `_private` names into tests.

## Commit hygiene

- One logical change per commit; don't combine unrelated changes.
- Keep pure moves/renames and pure refactors (no behaviour change) in their own
  commits, separate from functional changes.
- Tidy the history before pushing. Only commit when explicitly asked.

## How an AI agent should work here

- Make the smallest change that satisfies the task. Match existing patterns before
  inventing new ones.
- If a file is messy, you may clean the part you touch; don't silently rewrite
  unrelated code in the same change.
- State assumptions inline in the PR/response. If a decision is architectural
  (new dependency, new layer, storage change), ask first.
- Be direct and technical: state what the issue *is*, not what "might" be a
  problem. No softening filler.
- Always end by running `ruff`, `mypy`, and `pytest` and reporting the result.
-
## Conventions addendum

We follow Kraken-flavoured Python conventions where applicable to a solo FastAPI
project. These extend (never replace) the existing rules in this file.

### Runtime
- Target **Python 3.14** (latest patch). `.python-version`, `requires-python
    ">=3.14"`, ruff `target-version = "py314"`, and mypy/ruff/pytest bumped to their
    latest versions. If any dependency lacks 3.14 support at `uv sync`, STOP and
    report — do not pin workarounds silently.
- Rule 9 is retired: PEP 649 lazy annotations are the default in 3.14, so
    `from __future__ import annotations` is never needed. Never add it.
- t-strings (PEP 750) and other 3.14 features: use only where they make code
    plainly clearer. No novelty for its own sake.

### Architecture (Kraken layering)
- Layered monolith, dependencies point inward ONLY — see the Architecture and
    Package-layout sections above for the canonical chain. Enforced by
    **import-linter**: `lint-imports` reports **3 contracts** today (a "layers"
    contract, a "forbidden" contract barring `domain` from importing any sibling,
    plus one more — confirm the third in `.importlinter`). Runs in `make check`
    alongside ruff/mypy/pytest; it has replaced the old tests/test_architecture.py.
- Use-cases are **module-level functions, one concern per module** in `app/`
    (`plan_week.py`, `promotion.py`) — never service classes, never managers.
- The API layer only translates: parse request → call one app function → shape
    response. Zero business logic in routers, zero domain logic in api_models.
- SQLModel rows never cross the `storage/` boundary — repositories accept and
    return domain models. The ORM is an implementation detail.

### Functions (Kraken style)
- **Keyword-only arguments** (`*,`) for every function with more than one
    parameter, except where positional reads naturally (e.g. `diff_payloads(a, b)`).
- Prefer pure functions and immutable values (frozen Pydantic models, tuples,
    frozensets). Side effects live at the edges (app/storage/scripts), never in
    domain.
- No inheritance for code reuse — composition only. No mixins, no abstract base
    ceremony; a `Protocol` where a second implementation actually exists.
- Narrow, typed exceptions from the FoodiegramError hierarchy; raise early,
    catch at the edge that can act on it.

### Tests (Kraken style)
- Domain: pure unit tests, no mocks, no fixtures beyond plain constructors.
- App/storage: test through the public use-case function against the Postgres test
    DB (`DATABASE_URL_TEST`) — do not mock internal collaborators.
- Never mock what you own except at true external boundaries (OpenAI, Cloudinary,
    Instagram) — and there, fake the adapter, not the SDK internals.

### Frontend
- JS rules live in docs/PLAN.md Part VI §15 and are equally binding
    (`// @ts-check`, pure function components, `textContent` only, a11y as a
    review gate, `tsc --noEmit` in make check).

### Workflow
- Work from docs/PLAN.md Part VIII **one checklist item at a time**, strictly in
    order. Before coding, restate the item's acceptance criteria in one sentence.
    After coding, run the full gate: `ruff check --fix . && ruff format . && mypy .
    && pytest && lint-imports` (+ `tsc --noEmit` once frontend/ exists). Red = not
    done.
- If an MCP tool for the Notion board is available in this workspace, mark the
    matching task complete when a checklist item lands; otherwise end the session
    with a one-line status I can paste into Notion.
- When a decision is not covered by docs/PLAN.md or this file: STOP and ask.
    Do not invent scope. Deferred list = D16.
