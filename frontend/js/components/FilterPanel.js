// @ts-check

import { capitalise, humanise } from "../lib/format.js";

/** @typedef {import("../lib/filters.js").BrowseFilters} BrowseFilters */
/** @typedef {import("../lib/filters.js").SelectKey} SelectKey */

/**
 * @typedef {object} ProteinPill
 * @property {string} value MedCategory value sent as `protein_category`.
 * @property {string} label
 * @property {string} color CSS custom property naming the swatch colour.
 * @property {boolean} [ring] Draw the dot as an outline (the second hue member).
 */

/**
 * @typedef {object} Tier
 * @property {string} id
 * @property {string} label
 * @property {ProteinPill[]} pills
 */

/**
 * @typedef {object} SelectSpec
 * @property {SelectKey} key
 * @property {string} label
 * @property {string[]} values Enum values, in enum order; "" (Any) is added.
 */

/** The protein key grouped by how often it belongs in a week (domain/proteins.py). */
const TIERS = /** @type {Tier[]} */ ([
  {
    id: "tier-eat-freely",
    label: "Eat freely",
    pills: [
      { value: "fish", label: "Fish", color: "--cat-fish" },
      { value: "legumes", label: "Legumes", color: "--cat-legumes" },
      { value: "plant_protein", label: "Plant protein", color: "--cat-plant", ring: true },
    ],
  },
  {
    id: "tier-moderate",
    label: "Moderate",
    pills: [
      { value: "poultry", label: "Poultry", color: "--cat-poultry" },
      { value: "eggs", label: "Eggs", color: "--cat-eggs", ring: true },
      { value: "dairy", label: "Dairy", color: "--cat-dairy" },
    ],
  },
  {
    id: "tier-occasional",
    label: "Occasional",
    pills: [
      { value: "red_meat", label: "Red meat", color: "--cat-red-meat" },
      { value: "processed_meat", label: "Processed", color: "--cat-processed", ring: true },
    ],
  },
]);

/* The closed sets mirror domain/enums.py, minus "unknown" — filtering by "we do
 * not know" is not a question anyone asks. Dietary tags are an open list, so
 * these are the ones extraction actually emits. */
const SELECTS = /** @type {SelectSpec[]} */ ([
  {
    key: "dishType",
    label: "Dish type",
    values: [
      "soup", "salad", "main_course", "side_dish", "dessert", "beverage", "bread",
      "sauce", "snack", "pasta", "risotto", "pizza", "sandwich", "pastry",
    ],
  },
  {
    key: "mealType",
    label: "Meal",
    values: ["breakfast", "lunch", "dinner", "snack", "dessert", "appetizer"],
  },
  {
    key: "cuisine",
    label: "Cuisine",
    values: [
      "italian", "asian", "korean", "mexican", "mediterranean", "american",
      "french", "fusion", "other",
    ],
  },
  { key: "difficulty", label: "Difficulty", values: ["easy", "medium", "hard"] },
  {
    key: "dietaryTag",
    label: "Dietary",
    values: [
      "vegetarian", "vegan", "pescatarian", "gluten_free", "dairy_free",
      "low_carb", "keto", "paleo",
    ],
  },
]);

/**
 * @typedef {object} FilterPanelHandlers
 * @property {(category: string) => void} onToggleProtein
 * @property {(key: SelectKey, value: string) => void} onSelect
 * @property {() => void} onClear
 * @property {() => void} onApply Confirm and close; filtering already happened.
 */

/**
 * @typedef {object} FilterPanelView
 * @property {HTMLElement} element
 * @property {(filters: BrowseFilters, shown: number) => void} render
 * @property {() => void} focusFirst
 */

/**
 * The Filters panel: protein pills in three tiers, then the plain dropdowns.
 *
 * Choosing a facet filters straight away, so "Show N recipes" only confirms and
 * closes — it is the count you are about to get, not a submit button.
 * @param {FilterPanelHandlers} handlers
 * @returns {FilterPanelView}
 */
export function FilterPanel(handlers) {
  /** @type {Map<string, HTMLButtonElement>} */
  const pills = new Map();
  /** @type {Map<SelectKey, HTMLSelectElement>} */
  const selects = new Map();

  const panel = document.createElement("div");
  panel.className = "filters-panel";
  panel.hidden = true;

  const group = document.createElement("section");
  group.className = "filter-group";
  const heading = document.createElement("h2");
  heading.className = "filter-group__title";
  heading.textContent = "Protein";
  group.append(heading);
  for (const tier of TIERS) {
    group.append(buildTier(tier, pills, handlers.onToggleProtein));
  }

  const refine = document.createElement("div");
  refine.className = "filter-selects";
  for (const spec of SELECTS) {
    refine.append(buildSelect(spec, selects, handlers.onSelect));
  }

  const body = document.createElement("div");
  body.className = "filters-panel__body";
  body.append(group, refine);

  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "btn-ghost";
  clear.textContent = "Clear all";
  clear.addEventListener("click", handlers.onClear);

  const apply = document.createElement("button");
  apply.type = "button";
  apply.className = "btn-primary";
  apply.addEventListener("click", handlers.onApply);

  const footer = document.createElement("div");
  footer.className = "filters-panel__footer";
  footer.append(clear, apply);

  panel.append(body, footer);

  return {
    element: panel,

    render(filters, shown) {
      for (const [value, pill] of pills) {
        const pressed = filters.proteins.includes(value);
        pill.setAttribute("aria-pressed", String(pressed));
        pill.classList.toggle("protein-pill--active", pressed);
      }
      for (const [key, select] of selects) {
        select.value = filters[key];
      }
      apply.textContent = `Show ${shown.toLocaleString()} ${
        shown === 1 ? "recipe" : "recipes"
      }`;
    },

    focusFirst() {
      const first = pills.values().next().value;
      first?.focus();
    },
  };
}

/**
 * @param {Tier} tier
 * @param {Map<string, HTMLButtonElement>} registry
 * @param {(category: string) => void} onToggle
 * @returns {HTMLElement}
 */
function buildTier(tier, registry, onToggle) {
  const row = document.createElement("div");
  row.className = "filter-tier";
  row.setAttribute("role", "group");
  row.setAttribute("aria-labelledby", tier.id);

  const label = document.createElement("span");
  label.className = "filter-tier__label";
  label.id = tier.id;
  label.textContent = tier.label;

  const list = document.createElement("div");
  list.className = "filter-tier__pills";
  for (const pill of tier.pills) {
    const button = buildPill(pill, onToggle);
    registry.set(pill.value, button);
    list.append(button);
  }

  row.append(label, list);
  return row;
}

/**
 * A pill is always a dot *and* a word: colour alone is never the message.
 * @param {ProteinPill} pill
 * @param {(category: string) => void} onToggle
 * @returns {HTMLButtonElement}
 */
function buildPill(pill, onToggle) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "protein-pill";
  button.setAttribute("aria-pressed", "false");

  const dot = document.createElement("span");
  dot.className = pill.ring ? "protein-pill__dot protein-pill__dot--ring" : "protein-pill__dot";
  dot.style.setProperty("--dot", `var(${pill.color})`);
  dot.setAttribute("aria-hidden", "true");

  const text = document.createElement("span");
  text.textContent = pill.label;

  button.append(dot, text);
  button.addEventListener("click", () => onToggle(pill.value));
  return button;
}

/**
 * @param {SelectSpec} spec
 * @param {Map<SelectKey, HTMLSelectElement>} registry
 * @param {(key: SelectKey, value: string) => void} onSelect
 * @returns {HTMLElement}
 */
function buildSelect(spec, registry, onSelect) {
  const wrap = document.createElement("p");
  wrap.className = "filter-select";

  const select = document.createElement("select");
  select.className = "filter-select__input";
  select.id = `filter-${spec.key}`;
  select.append(buildOption("", "Any"));
  for (const value of spec.values) {
    select.append(buildOption(value, capitalise(humanise(value))));
  }
  select.addEventListener("change", () => onSelect(spec.key, select.value));
  registry.set(spec.key, select);

  const label = document.createElement("label");
  label.className = "filter-select__label";
  label.htmlFor = select.id;
  label.textContent = spec.label;

  wrap.append(label, select);
  return wrap;
}

/**
 * @param {string} value
 * @param {string} label
 * @returns {HTMLOptionElement}
 */
function buildOption(value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  return option;
}

/* ---- The button that opens the panel ------------------------------------ */

/**
 * @typedef {object} FiltersToggleView
 * @property {HTMLButtonElement} element
 * @property {(count: number) => void} render
 * @property {(open: boolean) => void} setOpen
 */

/**
 * The Filters button, carrying a count of how many facets are holding.
 * @param {() => void} onClick
 * @returns {FiltersToggleView}
 */
export function FiltersToggle(onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "filters-toggle";
  button.setAttribute("aria-expanded", "false");
  button.addEventListener("click", onClick);

  const label = document.createElement("span");
  label.textContent = "Filters";

  const badge = document.createElement("span");
  badge.className = "filters-toggle__count";
  badge.hidden = true;

  const caret = document.createElement("span");
  caret.className = "filters-toggle__caret";
  caret.setAttribute("aria-hidden", "true");
  caret.textContent = "\u203a";

  button.append(label, badge, caret);

  return {
    element: button,

    render(count) {
      badge.hidden = count === 0;
      badge.textContent = String(count);
      button.setAttribute(
        "aria-label",
        count === 0 ? "Filters" : `Filters, ${count} active`,
      );
    },

    setOpen(open) {
      button.setAttribute("aria-expanded", String(open));
      button.classList.toggle("filters-toggle--open", open);
    },
  };
}
