// @ts-check

import { CategoryChip } from "./CategoryChip.js";
import { displayTitle } from "../lib/format.js";

/** @typedef {import("../api/client.js").CategoryStatus} CategoryStatus */
/** @typedef {import("../api/client.js").GapSuggestion} GapSuggestion */
/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */

const MAX_SUGGESTIONS = 6;
const MAX_SEARCH_RESULTS = 8;
const SEARCH_DEBOUNCE_MS = 200;

/**
 * @typedef {object} GapSuggestionsHandlers
 * @property {(recipe: RecipeSummary) => void} onAdd
 * @property {(query: string) => Promise<RecipeSummary[]>} onSearch
 */

/**
 * @typedef {object} GapSuggestionsView
 * @property {HTMLElement} element
 * @property {(balance: CategoryStatus[], suggestions: GapSuggestion[]) => void} render
 * @property {() => void} focusFirst
 */

/**
 * The default "add to day" content (D20): a ranked, one-tap list of recipes
 * that fill whichever category is currently most under target, ahead of any
 * search. "Search all recipes" is a secondary, collapsed fallback.
 * @param {GapSuggestionsHandlers} handlers
 * @returns {GapSuggestionsView}
 */
export function GapSuggestions(handlers) {
  const wrap = document.createElement("div");
  wrap.className = "gap-suggestions";

  const list = document.createElement("ul");
  list.className = "gap-suggestions__list";

  const empty = document.createElement("p");
  empty.className = "gap-suggestions__empty";
  empty.textContent = "Nothing under target right now — search to add anything else.";
  empty.hidden = true;

  const searchToggle = document.createElement("button");
  searchToggle.type = "button";
  searchToggle.className = "btn-ghost gap-suggestions__search-toggle";
  searchToggle.textContent = "Search all recipes";
  searchToggle.setAttribute("aria-expanded", "false");

  const searchPanel = buildSearchPanel(handlers.onSearch, handlers.onAdd);
  searchPanel.element.hidden = true;

  searchToggle.addEventListener("click", () => {
    const open = searchPanel.element.hidden;
    searchPanel.element.hidden = !open;
    searchToggle.setAttribute("aria-expanded", String(open));
    if (open) {
      searchPanel.focusInput();
    }
  });

  wrap.append(list, empty, searchToggle, searchPanel.element);

  return {
    element: wrap,
    render(balance, suggestions) {
      const ranked = rankByDeficit(balance, suggestions);
      list.replaceChildren(...ranked.map((entry) => buildRow(entry, handlers.onAdd)));
      empty.hidden = ranked.length > 0;
    },
    focusFirst() {
      const firstButton = list.querySelector("button");
      if (firstButton instanceof HTMLElement) {
        firstButton.focus();
      } else {
        searchToggle.focus();
      }
    },
  };
}

/**
 * Flatten suggestions into a deduped, deficit-ranked list of (recipe,
 * category) pairs, capped for a one-glance list.
 * @param {CategoryStatus[]} balance
 * @param {GapSuggestion[]} suggestions
 * @returns {{ recipe: RecipeSummary, category: string }[]}
 */
function rankByDeficit(balance, suggestions) {
  const deficitByCategory = new Map(
    balance
      .filter((status) => status.state === "under")
      .map(
        (status) =>
          /** @type {[string, number]} */ ([
            status.category,
            status.min_servings - status.planned,
          ]),
      ),
  );

  const ranked = suggestions
    .filter((entry) => deficitByCategory.has(entry.category))
    .slice()
    .sort(
      (a, b) => (deficitByCategory.get(b.category) ?? 0) - (deficitByCategory.get(a.category) ?? 0),
    );

  /** @type {{ recipe: RecipeSummary, category: string }[]} */
  const flat = [];
  /** @type {Set<string>} */
  const seen = new Set();
  for (const entry of ranked) {
    for (const recipe of entry.recipes) {
      if (seen.has(recipe.code)) {
        continue;
      }
      seen.add(recipe.code);
      flat.push({ recipe, category: entry.category });
      if (flat.length >= MAX_SUGGESTIONS) {
        return flat;
      }
    }
  }
  return flat;
}

/**
 * @param {{ recipe: RecipeSummary, category?: string }} entry
 * @param {(recipe: RecipeSummary) => void} onAdd
 * @returns {HTMLLIElement}
 */
function buildRow(entry, onAdd) {
  const item = document.createElement("li");
  item.className = "gap-suggestions__row";

  const button = document.createElement("button");
  button.type = "button";
  button.className = "gap-suggestions__pick";
  button.addEventListener("click", () => onAdd(entry.recipe));

  if (entry.category) {
    const chip = CategoryChip(entry.category);
    chip.classList.add("gap-suggestions__chip");
    button.append(chip);
  }

  const title = document.createElement("span");
  title.className = "gap-suggestions__title";
  title.textContent = displayTitle(entry.recipe);

  button.append(title);
  item.append(button);
  return item;
}

/**
 * @typedef {object} SearchPanelView
 * @property {HTMLElement} element
 * @property {() => void} focusInput
 */

/**
 * @param {(query: string) => Promise<RecipeSummary[]>} onSearch
 * @param {(recipe: RecipeSummary) => void} onAdd
 * @returns {SearchPanelView}
 */
function buildSearchPanel(onSearch, onAdd) {
  const panel = document.createElement("div");
  panel.className = "gap-suggestions__search";

  const input = document.createElement("input");
  input.type = "search";
  input.className = "gap-suggestions__search-input";
  input.setAttribute("aria-label", "Search all recipes to add");
  input.placeholder = "search by name or ingredient…";

  const results = document.createElement("ul");
  results.className = "gap-suggestions__list";

  let timer = 0;
  let latestRequest = 0;

  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    const query = input.value.trim();
    timer = window.setTimeout(() => void runSearch(query), SEARCH_DEBOUNCE_MS);
  });

  /**
   * @param {string} query
   */
  async function runSearch(query) {
    const request = (latestRequest += 1);
    if (query === "") {
      results.replaceChildren();
      return;
    }
    const matches = await onSearch(query);
    if (request !== latestRequest) {
      return;
    }
    results.replaceChildren(
      ...matches.slice(0, MAX_SEARCH_RESULTS).map((recipe) => buildRow({ recipe }, onAdd)),
    );
  }

  panel.append(input, results);

  return {
    element: panel,
    focusInput() {
      input.focus();
    },
  };
}
