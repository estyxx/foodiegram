# CLAUDE.md — Working agreement for AI coding agents

> Drop this at the repo root. Cursor, Claude Code, and most agents read a root
> `CLAUDE.md` / `AGENTS.md` automatically. Keep it short enough that it actually
> gets followed. This is the contract: when in doubt, match what's here.

## What this project is

Foodiegram extracts saved Instagram posts from specific collections, uses an LLM
to turn captions into structured, richly tagged recipes, hosts the images durably,
and serves a browsable site for searching recipes and planning a week of meals.

Personal project. Bias hard toward **simple, robust, readable** over clever.

## Golden rules (non-negotiable)

1. **No `**kwargs` in our own code.** Every function signature is explicit and typed.
   (LLM/SDK boundary objects are the only exception, and even there, unpack into
   named fields immediately.)
2. **Type everything.** Code must pass `mypy --strict`. No bare `Any` unless
   genuinely unavoidable, and then with a `# reason:` comment.
3. **Never `print`.** Use the module `logger`. Never `traceback.print_exc()`.
4. **No bare `except Exception: pass`.** Catch the narrowest thing, log it, and
   either re-raise a typed error or return a typed result. See "Errors" below.
5. **Domain is pure.** Files in `domain/` do no I/O — no network, no disk, no env,
   no SDK clients. If you're importing `openai` or `instagrapi` there, stop.
6. **Don't add a dependency without asking.** We already have what we need.
7. **Before you call a task done:** `ruff check --fix . && ruff format . && mypy . && pytest`.
   Green or it isn't finished.

## Tooling

- **uv** for everything (`uv sync`, `uv run`, `uv add`). No `pip`, no `poetry`.
- **ruff** with `select = ["ALL"]` (current config). Don't silence a rule inline;
  if a rule is genuinely wrong for us, add it to `ignore` in `pyproject.toml` with
  a comment, repo-wide.
- **mypy** strict. **pytest** for tests. **pre-commit** runs ruff + mypy on commit.
- Python **3.13+** (bump to 3.14 only after confirming instagrapi/openai support).

## Typing & style

- **Inputs at the top.** Module-level inputs, constants, and config go at the top
  of the file, above the functions and classes that use them.
- `from __future__ import annotations` **only when you actually need it** (a forward
  reference or a self-referential model). On 3.13 our syntax already works at
  runtime, and a blanket future-import forces `# noqa: TC003` on imports Pydantic
  needs at runtime — so don't add it by default.
- Modern syntax: `str | None`, `list[str]`, `X | Y`. Never `Optional`, `List`, `Union`.
- Line length 89 (ruff config). Let the formatter win; don't hand-wrap.
- Public functions and classes get a one-line docstring, imperative mood, ending
  with a period (PEP 257). **No module-level docstrings** (`D100`/`D104` are
  ignored). Never write a docstring or comment that just restates the code —
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
- **Preserve original language.** Store the caption verbatim. Store
  `ingredients_original` (as written, IT/EN) *and* normalized English tags for
  filtering. Search must work in both languages — never overwrite the Italian.
- Instagram media URLs **expire**. Capture the image at extraction time and store
  the durable (Cloudinary) URL + `public_id`. Never persist a raw cdninstagram URL
  as the source of truth.

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

## Architecture (layered, DDD-lite — not full DDD)

Dependencies point **inward only**: interfaces → app → adapters → domain.
Domain depends on nothing.

```
domain/      pure models, enums, errors. No I/O. No SDKs.
instagram/   instagrapi adapter + caching. Knows about Media; maps it to domain.
ai/          LLM extraction: prompts (as .txt files), schema, batch + interactive.
images/      Cloudinary adapter. Download → upload → return durable URL/public_id.
storage/     repository: JSON now, SQLite later, same interface.
app/         services / use-cases. Thin orchestration of the above. No business
             logic leaking into adapters.
settings.py  pydantic-settings (BaseSettings). Loads + validates env. Never logged.
cli.py       typer entrypoints (fetch / analyze / build).
api.py       FastAPI (added in Phase 3, not before).
```

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
- `temperature=0` (or near) for extraction — we want determinism, not creativity.

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
