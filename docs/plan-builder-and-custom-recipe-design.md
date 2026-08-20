# Plan Builder + custom recipes — design exploration (Session 1)

Companion to `docs/PLAN.md` (Phase 4 and Phase 6) and `ios-share-capture-plan.md`.
This doc captures a design conversation, not committed code — read it before
picking either thread back up.

## Scope

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

## Decisions this session (continuing the D-numbering from PLAN.md §... D16)

| # | Decision |
|---|---|
| D17 | `Recipe` gains `inspired_by: list[str] = []` — codes of any recipe (Instagram *or* manual) that inspired this one. Chaining is allowed: a remix of a remix just lists its immediate parent(s). Generalizes D16's `parent_code` idea from one link to a list, since a custom recipe may combine ideas from more than one saved post. |
| D18 | **Open** — which surface produces an `inspired_by` recipe. Leaning chat-driven for now (search/get via MCP → draft together → save via a script that calls the same `RecipeRepository.save()` Phase 6.2 will eventually expose as an in-app form), so nothing built now needs to be rebuilt later. Revisit once Phase 6 is in view. |
| D19 | Plan Builder build order: **balance panel + day columns first** (PLAN.md's "wow moment," 4.4), ahead of pantry/cookable-now (Phase 5) and the shopping list. |
| D20 | Primary ADHD lens for this screen: **low decision fatigue**. The "add to day" interaction defaults to ranked gap-suggestions, not a search box — see below. |
| D21 | `week_start` stays the `/api/plans/{week_start}` identifier, unchanged. A full ISO date never recurs, so this is stable for as many years as the app runs, and the DB already backs it with a surrogate `WeekPlanRow.id` (meals FK to that, not to the date) — the "solid" part was already built. **No user/household scoping added now** — every table (`week_plans`, `pantry_items`, `user_state`, `targets`) is unscoped today, consistent with D13's single-credential, zero-login-UI, solo-hobby-project stance. Deferred deliberately, not overlooked: because storage already uses surrogate keys everywhere, adding a `user_id` column + tightening `week_start`'s unique constraint to `(user_id, week_start)` later is a mechanical, low-risk migration, not a redesign. Revisit only if this ever needs to serve more than one person's plan. |

## Entity shape

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

## Workflow sketch (still marked open per D18)

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

## Plan Builder v1 slice (balance panel + day columns)

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

## Open questions for next round

- Does `inspired_by` need to resolve/display in the UI (e.g. "riffed on
  Pasta e Ceci") or is it just backend provenance for now?
- Where's the line for "this needs a nicer surface than a script" — some
  number of custom recipes, or just whenever Phase 6 comes around anyway?
- Should the Plan Builder's gap-suggestion shortlist prefer *your* custom
  recipes over Instagram ones, once some exist, or stay neutral?
