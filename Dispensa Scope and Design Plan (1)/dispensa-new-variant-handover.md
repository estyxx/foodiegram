# Dispensa — New Variant Handover

**Goal:** create a *third*, genuinely different visual variant of Dispensa — same fundamentals and data, new style. Two directions already exist (a calm one and a bold print-craft one); don't reuse either look.

**How to start the new chat:** paste the prompt below, and attach `dispensa-data.json` from this project.

---

## PROMPT (paste into the new chat)

I'm building **Dispensa**, a warm, editorial recipe-browsing & meal-planning web app for cooking a week of meals to Mediterranean-diet guidelines, while tracking what's already in the fridge/freezer/pantry. Two design directions already exist elsewhere (a calm one and a bold print-craft one). **I want a third, genuinely different visual variant — same fundamentals and data, new style.** Don't reuse the previous two looks; explore a new aesthetic direction (different type-pairing feel, layout metaphor, colour application, texture). Keep it warm, calm, ADHD-friendly, and accessible.

**Use the attached `dispensa-data.json` for all content — don't regenerate recipes.**

Build it as a single Design Component, desktop-first but responsive. **Three screens, navigable:** Home ("This Week"), Plan Builder, Recipe Detail. (Browse and Goals & Profile come later.) Start high-fidelity static, interactions wired after.

### These fundamentals are fixed — only the style changes

**The 7-category colour key** (the heart of the product — quantitatively tracked, reused identically everywhere: weekly-balance panel, day chips, recipe badges, Plan chips). Cooler = eat more, warmer = eat less; every colour always paired with a text label or icon, never colour alone:

- Fish & seafood — teal (light) — target 2–3/wk — "at least twice a week; ≥1 oily fish"
- Legumes — forest green — 2–3/wk — "≥2–3 a week"
- Poultry — mustard — ~2/wk — "moderate"
- Eggs — mustard outline — 2–4/wk — "2–4 a week"
- Dairy & cheese — teal (dark) — moderate daily-to-weekly — "small portions; limit hard cheese"
- Red meat — coral — ≤2 ideally ≤1 — "occasional, lean cuts"
- Processed meat — coral outline — ≤1 ideally 0 — "rarely"

A recipe can count toward **more than one** tracked category (e.g. lentil-parmesan soup = legumes + dairy) — add it to every category it touches. A live **weekly balance panel** (one row per category) fills toward target and flags over/under; when short, suggest recipes that fill the gap. Adding/removing recipes must move the balance in real time — that's the demo's wow moment.

**Daily base (NOT in the balance panel, quiet neutral outlined chips):** vegetables, fruit, whole grains, olive oil, nuts/seeds, herbs & spices.

**Plant-based badge** — separate from the 7-key and the neutral chips: vegetarian/vegan recipes get one distinct leaf badge, in a palette colour that is NOT the legumes green. Shown on cards, never in the balance panel.

**Palette properties (derive new specific hues for the new style):** one paper-like warm background, one deep ink for text, ~3–4 desaturated warm accents. No pure/neon colour. Cues from Mediterranean ingredients/produce/herbs/oil. WCAG AA minimum (AAA preferred) for text on the paper ground.

**Type system has three jobs:** a characterful display serif (with italic flourish) for titles/hero; a monospace for short functional tokens only (labels, dates, quantities+units, tags, badges); a quiet body sans (or serif regular) for prose (method steps, descriptions). All three must render Italian accents cleanly (à è ò ù) — several recipes are Italian-titled.

### Screen specifics

- **Home:** editorial hero + week dates/theme; the weekly balance panel as the first thing seen; a 7-day Mon–Sun strip with planned meals as category-coloured chips (empty days clearly invite planning); a "Cook tonight" highlight linking to Recipe Detail; a quiet "From your kitchen" strip (2–3 recipes mostly makeable from stock, flag expiring items); primary CTA "Plan the week."
- **Plan Builder:** two-pane. Left = 7 day-columns with meal slots, add/remove recipes (chips in category colour), pantry count per chip ("7/9 in kitchen"). Right (sticky) = live balance panel + a "fills a gap" suggestion list + "Generate shopping list" (missing items, grouped by aisle, de-duplicated). Drag-and-drop must have a keyboard alternative ("add to day" menu) and announce changes via live region.
- **Recipe Detail:** magazine page. Display-serif title (italic accent word, Italian-safe), one-line description, mono metadata row (prep/cook time, servings, difficulty, cuisine). A "Mediterranean fit" line naming the tracked category(ies). Ingredients one per line: quantity+unit in mono, ingredient name in body font (not mono), per-ingredient in-kitchen/to-buy indicator. **Two scaling modes, both real:** (1) by servings (stepper rescales all), (2) by ingredient (type the amount you actually have for one ingredient, everything rescales off that ratio). Numbered method steps in body font. Actions: save/favourite, add to a day, add missing to shopping list.

### Accessibility (hard requirement)

AA+ contrast, never colour alone, full keyboard nav, visible focus rings (forest green or coral), skip-to-content link, semantic HTML + ARIA, real `<label>`s, `prefers-reduced-motion`, ≥44px hit targets, readable line lengths, mobile (filters → sheet, week strip scrolls horizontally, balance panel stays reachable).

### Data

Use the attached `dispensa-data.json`: 16 sample recipes across all tracked categories (incl. 3 Italian-titled and several multi-category), the category key, daily-base, collections, and a sample planned week. Pantry/fridge awareness ("in kitchen", "cookable now", shopping list) is aspirational placeholder data — design it well anyway.

Keep it warm, calm, confident — less dashboard, more well-set table. Ask me any clarifying questions about the new visual direction before building.

---

## Files to attach

- `dispensa-data.json` — all content (recipes, category key, week, collections). Framework-agnostic.

## What's intentionally NOT carried over

- Specific hex values, fonts, shadows, border-radii — the new variant should invent its own look from the *properties* above.
- Browse and Goals & Profile screens — out of scope for the first pass.
