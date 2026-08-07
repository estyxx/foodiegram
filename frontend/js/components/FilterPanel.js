// @ts-check

import { SELECTS, TIERS } from "../lib/facets.js";
import { capitalise, humanise } from "../lib/format.js";

/** @typedef {import("../lib/filters.js").BrowseFilters} BrowseFilters */
/** @typedef {import("../lib/filters.js").SelectKey} SelectKey */
/** @typedef {import("../lib/facets.js").SelectSpec} SelectSpec */
/** @typedef {import("../lib/facets.js").Tier} Tier */
/** @typedef {import("../lib/facets.js").ProteinPill} ProteinPill */

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
      // "Show 0 recipes" invites a tap that does nothing. Say so instead, and
      // let the empty state below offer the way out.
      apply.disabled = shown === 0;
      apply.textContent =
        shown === 0
          ? "No matches"
          : `Show ${shown.toLocaleString()} ${shown === 1 ? "recipe" : "recipes"}`;
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
