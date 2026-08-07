// @ts-check

import { getAllRecipes, getRecipeCounts, updateRecipe } from "../api/client.js";
import { FilterPanel, FiltersToggle } from "../components/FilterPanel.js";
import { RecipeCard } from "../components/RecipeCard.js";
import { SearchBar } from "../components/SearchBar.js";
import { SEGMENTS, segmentCount, segmentHint } from "../lib/facets.js";
import {
  activeCount,
  cleared,
  emptyFilters,
  isNarrowed,
  relaxations,
  toQuery,
  withIngredient,
  withProteinToggled,
  withSelect,
  withoutIngredient,
} from "../lib/filters.js";

const PAGE_SIZE = 50;

/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */
/** @typedef {import("../api/client.js").RecipeCounts} RecipeCounts */
/** @typedef {import("../lib/filters.js").BrowseFilters} BrowseFilters */
/** @typedef {import("../lib/filters.js").Segment} Segment */

/**
 * Render the browse (or favourites) view into container.
 * @param {HTMLElement} container
 * @param {{ favourites?: boolean }} [options]
 * @returns {Promise<void>}
 */
export async function renderBrowse(container, options) {
  const favourites = options?.favourites ?? false;
  container.replaceChildren();

  let filters = emptyFilters();
  /** @type {RecipeCounts} */
  let counts = { complete: 0, recipes: 0, all_saves: 0 };
  // Typing fires a request per keystroke; only the newest answer may land.
  let latestRequest = 0;

  const searchBar = SearchBar({
    onQueryChange: (text) => void apply({ ...filters, query: text }),
    onAddIngredient: (term) => void apply(withIngredient(filters, term)),
    onRemoveIngredient: (term) => void apply(withoutIngredient(filters, term)),
  });

  const panel = FilterPanel({
    onToggleProtein: (category) => void apply(withProteinToggled(filters, category)),
    onSelect: (key, value) => void apply(withSelect(filters, key, value)),
    onClear: () => void apply(cleared(filters)),
    onApply: () => setPanelOpen(false),
  });
  panel.element.id = "browse-filters";

  let panelOpen = false;
  const toggle = FiltersToggle(() => setPanelOpen(!panelOpen));
  toggle.element.setAttribute("aria-controls", panel.element.id);

  const toolbar = document.createElement("div");
  toolbar.className = "browse__toolbar";
  toolbar.append(searchBar.element, toggle.element);

  const commandBar = document.createElement("div");
  commandBar.className = "command-bar";
  commandBar.append(toolbar, panel.element);
  // Escape from anywhere in the bar, not just inside the panel: on mobile the
  // sheet covers the page and the search field is where the caret usually is.
  commandBar.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && panelOpen) {
      setPanelOpen(false);
    }
  });

  const summary = document.createElement("p");
  summary.className = "browse__count";
  summary.setAttribute("aria-live", "polite");

  // Built once and only relabelled, so a keyboard press keeps its focus on the
  // button that was activated.
  const segmentButtons = SEGMENTS.map((segment) =>
    buildSegment(segment, segment.value === filters.segment, () => {
      void setSegment(segment.value);
    }),
  );

  const segmented = document.createElement("div");
  segmented.className = "segmented";
  segmented.setAttribute("role", "group");
  segmented.setAttribute("aria-label", "Which saves to show");
  segmented.append(...segmentButtons);

  // The tier names are a ladder, and a ladder needs a rung label: on its own
  // "All recipes" does not admit that it includes the half-extracted ones.
  const segmentHintText = document.createElement("p");
  segmentHintText.className = "segmented__hint";
  segmentHintText.id = "browse-segment-hint";
  segmented.setAttribute("aria-describedby", segmentHintText.id);

  const tiers = document.createElement("div");
  tiers.className = "browse__tiers";
  tiers.append(segmented, segmentHintText);

  const resultsBar = document.createElement("div");
  resultsBar.className = "browse__results-bar";
  resultsBar.append(summary, tiers);

  const grid = document.createElement("div");
  grid.className = "recipe-grid";

  const loadMore = document.createElement("div");
  loadMore.className = "load-more";
  const loadMoreButton = document.createElement("button");
  loadMoreButton.type = "button";
  loadMoreButton.className = "load-more__btn";
  loadMoreButton.addEventListener("click", renderMore);
  loadMore.append(loadMoreButton);

  container.append(buildHero(favourites), commandBar, resultsBar, grid, loadMore);

  /** @type {RecipeSummary[]} Server results under the current filters. */
  let results = [];
  let rendered = 0;

  /**
   * @param {BrowseFilters} next
   * @returns {Promise<void>}
   */
  async function apply(next) {
    filters = next;
    await refetch();
  }

  async function refetch() {
    const query = toQuery(filters, { favourites });
    const request = (latestRequest += 1);
    const [fetched, fetchedCounts] = await Promise.all([
      getAllRecipes(query),
      getRecipeCounts(query),
    ]);
    if (request !== latestRequest) {
      return;
    }
    results = fetched;
    counts = fetchedCounts;
    renderAll();
  }

  /**
   * @param {Segment} next
   * @returns {Promise<void>}
   */
  async function setSegment(next) {
    if (next === filters.segment) {
      return;
    }
    await apply({ ...filters, segment: next });
  }

  /**
   * How many recipes a segment holds under the filters now in force.
   * @param {Segment} segment
   * @returns {number}
   */
  function countFor(segment) {
    return segmentCount(counts, segment);
  }

  /**
   * @param {boolean} open
   */
  function setPanelOpen(open) {
    panelOpen = open;
    panel.element.hidden = !open;
    toggle.setOpen(open);
    if (open) {
      panel.focusFirst();
    } else if (panel.element.contains(document.activeElement)) {
      toggle.element.focus();
    }
  }

  function renderAll() {
    searchBar.render(filters.ingredients);
    toggle.render(activeCount(filters));
    panel.render(filters, countFor(filters.segment));
    renderSegmented();
    renderResults();
  }

  function renderSegmented() {
    SEGMENTS.forEach((segment, index) => {
      const button = segmentButtons[index];
      setPressed(button, segment.value === filters.segment);
      const total = countFor(segment.value);
      const count = button.querySelector(".segmented__count");
      if (count) {
        count.textContent = total.toLocaleString();
      }
      button.setAttribute(
        "aria-label",
        `${segment.label}, ${total.toLocaleString()} recipes`,
      );
    });
    segmentHintText.textContent = segmentHint(filters.segment);
  }

  function renderResults() {
    grid.replaceChildren();
    rendered = 0;
    if (results.length === 0) {
      grid.append(...buildEmptyState(filters, counts, apply));
      updateCount();
      loadMore.hidden = true;
      return;
    }
    renderMore();
  }

  /** Append the next page of cards from the loaded result set. */
  function renderMore() {
    const next = results.slice(rendered, rendered + PAGE_SIZE);
    for (const recipe of next) {
      grid.append(RecipeCard(recipe, { onToggleFavourite }));
    }
    rendered += next.length;
    updateCount();
    const remaining = results.length - rendered;
    loadMore.hidden = remaining <= 0;
    if (remaining > 0) {
      loadMoreButton.textContent = `Load ${Math.min(PAGE_SIZE, remaining)} more \u2193`;
    }
  }

  function updateCount() {
    summary.textContent = `Showing ${rendered} of ${results.length} ${
      results.length === 1 ? "recipe" : "recipes"
    }`;
  }

  /**
   * @param {RecipeSummary} recipe
   */
  async function onToggleFavourite(recipe) {
    await updateRecipe(recipe.code, { is_favorite: !recipe.is_favorite });
    await refetch();
  }

  await refetch();
}

/* ---- Empty state -------------------------------------------------------- */

/**
 * @param {BrowseFilters} filters
 * @param {RecipeCounts} counts
 * @param {(next: BrowseFilters) => void} onRelax
 * @returns {HTMLElement[]}
 */
function buildEmptyState(filters, counts, onRelax) {
  const message = document.createElement("p");
  message.className = "state-msg";
  message.textContent = isNarrowed(filters)
    ? "No recipes match these filters."
    : "Nothing saved here yet.";

  /** @type {HTMLElement[]} */
  const parts = [message];

  if (filters.proteins.length > 0) {
    // A protein pill also hides every recipe with no protein recorded, which
    // is a quarter of the complete ones. Say so rather than let it read as
    // "you have none of these".
    const note = document.createElement("p");
    note.className = "state-msg state-msg--note";
    note.textContent =
      "A protein filter also hides every recipe with no protein recorded yet.";
    parts.push(note);
  }

  const ways = relaxations(filters, counts);
  if (ways.length > 0) {
    parts.push(buildRelaxations(ways, onRelax));
  }
  return parts;
}

/**
 * @param {import("../lib/filters.js").Relaxation[]} ways
 * @param {(next: BrowseFilters) => void} onRelax
 * @returns {HTMLElement}
 */
function buildRelaxations(ways, onRelax) {
  const wrap = document.createElement("div");
  wrap.className = "state-actions";
  for (const way of ways) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "state-action";
    button.textContent = way.label;
    button.addEventListener("click", () => onRelax(way.filters));
    wrap.append(button);
  }
  return wrap;
}

/* ---- Hero --------------------------------------------------------------- */

/**
 * @param {boolean} favourites
 * @returns {HTMLElement}
 */
function buildHero(favourites) {
  const hero = document.createElement("header");
  hero.className = "browse__hero";

  const eyebrow = document.createElement("p");
  eyebrow.className = "browse__eyebrow";
  eyebrow.textContent = favourites ? "Your picks" : "The collection";

  const title = document.createElement("h1");
  title.className = "browse__hero-title";
  const emphasis = document.createElement("em");
  if (favourites) {
    title.append(document.createTextNode("Your "), withText(emphasis, "saved picks"));
  } else {
    title.append(
      document.createTextNode("Browse every "),
      withText(emphasis, "saved recipe"),
    );
  }

  const subtitle = document.createElement("p");
  subtitle.className = "browse__hero-sub";
  subtitle.textContent = favourites
    ? "The recipes you\u2019ve starred. Filter by what the week needs, or search by name or ingredient."
    : "Everything pulled from your Instagram saves. Filter by what the week needs, or search by name or ingredient.";

  hero.append(eyebrow, title, subtitle);
  return hero;
}

/**
 * @param {HTMLElement} el
 * @param {string} text
 * @returns {HTMLElement}
 */
function withText(el, text) {
  el.textContent = text;
  return el;
}

/* ---- Is-recipe segmented control ---------------------------------------- */

/**
 * A segment carries both label lengths; CSS picks one by width, so the control
 * narrows without a resize listener. The count is the same either way.
 * @param {import("../lib/facets.js").SegmentSpec} spec
 * @param {boolean} pressed
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function buildSegment(spec, pressed, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "segmented__option";

  const full = document.createElement("span");
  full.className = "segmented__label segmented__label--full";
  full.textContent = spec.label;

  const short = document.createElement("span");
  short.className = "segmented__label segmented__label--short";
  short.textContent = spec.short;

  const count = document.createElement("span");
  count.className = "segmented__count";

  button.append(full, short, count);
  setPressed(button, pressed);
  button.addEventListener("click", onClick);
  return button;
}

/**
 * @param {HTMLButtonElement} button
 * @param {boolean} pressed
 */
function setPressed(button, pressed) {
  button.classList.toggle("segmented__option--active", pressed);
  button.setAttribute("aria-pressed", String(pressed));
}
