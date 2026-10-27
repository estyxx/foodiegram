// @ts-check

import { ProteinChips } from "./ProteinChip.js";
import { emptyFilters } from "../lib/filters.js";
import { displayTitle } from "../lib/format.js";
import { searchLocally } from "../lib/localFilter.js";

/** @typedef {import("../api/client.js").CategoryStatus} CategoryStatus */
/** @typedef {import("../api/client.js").RecipeIndex} RecipeIndex */
/** @typedef {import("../api/client.js").RecipeIndexEntry} RecipeIndexEntry */

/** @typedef {"gap" | "all" | "ig"} PickerFilter */

/** @type {[PickerFilter, string][]} */
const FILTERS = [
  ["gap", "Fills a gap"],
  ["all", "All"],
  ["ig", "From Instagram"],
];

// Enough to scroll through; typing narrows the rest.
const MAX_ROWS = 60;

/**
 * What the picker is filling. Rebuilt by the view after every plan change so
 * "In this slot" and the gap filter follow the live balance.
 * @typedef {object} PickerContext
 * @property {string} kicker "MAR 27 ott · Dinner".
 * @property {boolean} replacing True for "Change": pick swaps one dish.
 * @property {string[]} current Titles already in the slot.
 * @property {Set<string>} inSlot Codes already in the slot.
 * @property {CategoryStatus[]} balance
 * @property {RecipeIndex | null} index Null when the index failed to load.
 */

/**
 * @typedef {object} PickerHandlers
 * @property {(recipe: RecipeIndexEntry) => void} onPick
 * @property {(base: RecipeIndexEntry | null) => void} onCustom "My version of…"
 *   a recipe, or one written from scratch (D23).
 * @property {() => void} onClose Fires however the picker closes.
 */

/**
 * @typedef {object} RecipePickerView
 * @property {HTMLDialogElement} element
 * @property {(context: PickerContext) => void} open
 * @property {(context: PickerContext) => void} update
 * @property {() => void} noteAdded Count an add for the footer note.
 * @property {() => void} close
 * @property {() => boolean} isOpen
 */

/**
 * The add/change picker: a right-hand drawer on desktop, a bottom sheet on
 * mobile (CSS decides). A native modal <dialog> traps focus and closes on
 * Escape; a click on the backdrop closes it too.
 * @param {PickerHandlers} handlers
 * @returns {RecipePickerView}
 */
export function RecipePicker(handlers) {
  const dialog = document.createElement("dialog");
  dialog.className = "picker";
  dialog.setAttribute("aria-labelledby", "picker-title");

  const panel = document.createElement("div");
  panel.className = "picker__panel";

  const head = document.createElement("div");
  head.className = "picker__head";

  const titleRow = document.createElement("div");
  titleRow.className = "picker__title-row";
  const titles = document.createElement("div");
  titles.className = "picker__titles";
  const kicker = document.createElement("div");
  kicker.className = "picker__kicker";
  const title = document.createElement("h2");
  title.className = "picker__title";
  title.id = "picker-title";
  const current = document.createElement("div");
  current.className = "picker__current";
  titles.append(kicker, title, current);

  const close = document.createElement("button");
  close.type = "button";
  close.className = "picker__close";
  close.textContent = "×";
  close.setAttribute("aria-label", "Close");
  close.addEventListener("click", () => dialog.close());
  titleRow.append(titles, close);

  const search = document.createElement("label");
  search.className = "picker__search";
  const glass = document.createElement("span");
  glass.className = "picker__glass";
  glass.setAttribute("aria-hidden", "true");
  glass.textContent = "⌕";
  const searchLabel = document.createElement("span");
  searchLabel.className = "visually-hidden";
  searchLabel.textContent = "Search recipes";
  const input = document.createElement("input");
  input.type = "search";
  input.className = "picker__input";
  input.placeholder = "Search recipes";
  input.addEventListener("input", () => {
    query = input.value;
    renderList();
  });
  search.append(glass, searchLabel, input);

  const filters = document.createElement("div");
  filters.className = "picker__filters";
  filters.setAttribute("role", "tablist");
  filters.setAttribute("aria-label", "Filter");

  const gapNote = document.createElement("div");
  gapNote.className = "picker__note";

  head.append(titleRow, search, filters, gapNote);

  const list = document.createElement("div");
  list.className = "picker__list";

  const foot = document.createElement("div");
  foot.className = "picker__foot";
  const footNote = document.createElement("span");
  footNote.className = "picker__foot-note";
  const done = document.createElement("button");
  done.type = "button";
  done.className = "picker__done";
  done.textContent = "Done";
  done.addEventListener("click", () => dialog.close());
  foot.append(footNote, done);

  panel.append(head, list, foot);
  dialog.append(panel);

  // Clicks on the ::backdrop land on the dialog itself; the panel fills the
  // dialog box, so anything inside it has a different target.
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.close();
    }
  });
  dialog.addEventListener("close", () => handlers.onClose());

  /** @type {PickerContext | null} */
  let context = null;
  /** @type {PickerFilter} */
  let filter = "gap";
  let query = "";
  let added = 0;

  function renderHead() {
    if (context === null) {
      return;
    }
    kicker.textContent = context.kicker;
    title.textContent = context.replacing ? "Change dish" : "Add a dish";
    current.hidden = context.current.length === 0;
    // Each title cut at its first comma or bracket: the dish, not its notes.
    current.textContent = `In this slot: ${context.current
      .map((name) => name.split(/[,(]/)[0].trim())
      .join(" + ")}`;

    filters.replaceChildren(
      ...FILTERS.map(([key, label]) => {
        const tab = document.createElement("button");
        tab.type = "button";
        tab.className = "picker__filter";
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-selected", String(filter === key));
        tab.textContent = label;
        tab.addEventListener("click", () => {
          filter = key;
          renderHead();
          renderList();
        });
        return tab;
      }),
    );

    const gaps = gapCategories(context.balance);
    gapNote.hidden = filter !== "gap";
    gapNote.textContent =
      gaps.length > 0
        ? `Room left this week in ${gaps.map((status) => categoryWords(status.category)).join(", ")}.`
        : "Every category is on track or over. Try All.";

    foot.hidden = context.replacing;
    footNote.textContent =
      added > 0 ? `${added} added. Add more or finish.` : "You can add more than one dish.";
  }

  function renderList() {
    if (context === null) {
      return;
    }
    if (context.index === null) {
      list.replaceChildren(emptyRow("Couldn't load your recipes — close and try again."));
      return;
    }
    const matches = candidates(context.index, context.balance, filter, query);
    const rows = matches.slice(0, MAX_ROWS).map((recipe) => buildRow(recipe));
    if (matches.length === 0) {
      rows.push(emptyRow("No recipes match."));
    } else if (matches.length > MAX_ROWS) {
      rows.push(emptyRow(`Showing ${MAX_ROWS} of ${matches.length}. Search to narrow.`));
    }
    const own = document.createElement("button");
    own.type = "button";
    own.className = "picker__own";
    own.textContent = "Write my own recipe";
    own.addEventListener("click", () => handlers.onCustom(null));
    rows.push(own);
    list.replaceChildren(...rows);
  }

  /**
   * @param {RecipeIndexEntry} recipe
   * @returns {HTMLElement}
   */
  function buildRow(recipe) {
    const here = context?.inSlot.has(recipe.code) ?? false;
    const name = displayTitle(recipe);

    const row = document.createElement("div");
    row.className = "picker__row";

    const pick = document.createElement("button");
    pick.type = "button";
    pick.className = "picker__pick";
    // The server keeps one row per recipe per slot, so a repeat is a no-op.
    pick.disabled = here;
    pick.addEventListener("click", () => handlers.onPick(recipe));

    const body = document.createElement("span");
    body.className = "picker__body";
    const rowTitle = document.createElement("span");
    rowTitle.className = "picker__row-title";
    rowTitle.textContent = name;
    const meta = document.createElement("span");
    meta.className = "picker__meta";
    const chips = ProteinChips(recipe.category_servings);
    if (chips) {
      meta.append(...chips.children);
    }
    const facts = [recipe.total_time, recipe.author_username ? `@${recipe.author_username}` : null]
      .filter(Boolean)
      .join(" · ");
    if (facts) {
      const factsEl = document.createElement("span");
      factsEl.className = "picker__facts";
      factsEl.textContent = facts;
      meta.append(factsEl);
    }
    body.append(rowTitle, meta);

    const act = document.createElement("span");
    act.className = "picker__act";
    act.classList.toggle("picker__act--here", here);
    act.textContent = here ? "in slot" : context?.replacing ? "Use" : "+ Add";
    pick.append(body, act);

    const mine = document.createElement("button");
    mine.type = "button";
    mine.className = "picker__mine";
    mine.textContent = "Mine";
    mine.setAttribute("aria-label", `Make my version of ${name}`);
    mine.addEventListener("click", () => handlers.onCustom(recipe));

    row.append(pick, mine);
    return row;
  }

  return {
    element: dialog,
    open(next) {
      context = next;
      filter = next.replacing ? "all" : "gap";
      query = "";
      added = 0;
      input.value = "";
      renderHead();
      renderList();
      dialog.showModal();
      list.scrollTop = 0;
      input.focus();
    },
    update(next) {
      context = next;
      renderHead();
      renderList();
    },
    noteAdded() {
      added += 1;
      renderHead();
    },
    close() {
      if (dialog.open) {
        dialog.close();
      }
    },
    isOpen() {
      return dialog.open;
    },
  };
}

/**
 * Categories with room left this week, in balance order.
 * @param {CategoryStatus[]} balance
 * @returns {CategoryStatus[]}
 */
function gapCategories(balance) {
  return balance.filter((status) => status.state === "under");
}

/**
 * "plant protein" for the gap note's running prose.
 * @param {string} category
 * @returns {string}
 */
function categoryWords(category) {
  return category.replace(/_/g, " ").replace("processed meat", "processed");
}

/**
 * The recipes a filter and query leave, best gap-fillers first under "Fills
 * a gap", alphabetical otherwise.
 * @param {RecipeIndex} index
 * @param {CategoryStatus[]} balance
 * @param {PickerFilter} filter
 * @param {string} query
 * @returns {RecipeIndexEntry[]}
 */
function candidates(index, balance, filter, query) {
  const { results } = searchLocally(
    index,
    { ...emptyFilters(), query: query.trim(), segment: "recipes" },
    { favourites: false },
  );
  const byTitle = (/** @type {RecipeIndexEntry} */ a, /** @type {RecipeIndexEntry} */ b) =>
    displayTitle(a).localeCompare(displayTitle(b), "it");
  if (filter === "ig") {
    return results.filter((recipe) => recipe.author_username !== null).sort(byTitle);
  }
  if (filter === "all") {
    return [...results].sort(byTitle);
  }
  const gaps = new Set(gapCategories(balance).map((status) => status.category));
  const fill = (/** @type {RecipeIndexEntry} */ recipe) =>
    recipe.category_servings
      .filter((serving) => gaps.has(serving.category))
      .reduce((sum, serving) => sum + serving.servings, 0);
  return results
    .map((recipe) => ({ recipe, fill: fill(recipe) }))
    .filter((entry) => entry.fill > 0)
    .sort((a, b) => b.fill - a.fill || byTitle(a.recipe, b.recipe))
    .map((entry) => entry.recipe);
}

/**
 * @param {string} text
 * @returns {HTMLElement}
 */
function emptyRow(text) {
  const row = document.createElement("div");
  row.className = "picker__empty";
  row.textContent = text;
  return row;
}
