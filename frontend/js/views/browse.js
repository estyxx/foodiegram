// @ts-check

import { getAllRecipes, getRecipeCounts, updateRecipe } from "../api/client.js";
import { FilterPanel, FiltersToggle } from "../components/FilterPanel.js";
import { RecipeCard } from "../components/RecipeCard.js";
import { SearchBar } from "../components/SearchBar.js";
import {
  activeCount,
  cleared,
  emptyFilters,
  isNarrowed,
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
  let counts = { recipes_only: 0, all_saves: 0 };
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

  // Both segments are built once and only relabelled, so a keyboard toggle keeps
  // its focus on the button that was activated.
  const recipesSegment = buildSegment("Recipes only", filters.recipesOnly, () => {
    void setRecipesOnly(true);
  });
  const allSavesSegment = buildSegment("All saves", !filters.recipesOnly, () => {
    void setRecipesOnly(false);
  });

  const segmented = document.createElement("div");
  segmented.className = "segmented";
  segmented.setAttribute("role", "group");
  segmented.setAttribute("aria-label", "Which saves to show");
  segmented.append(recipesSegment, allSavesSegment);

  const resultsBar = document.createElement("div");
  resultsBar.className = "browse__results-bar";
  resultsBar.append(summary, segmented);

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
   * @param {boolean} next
   * @returns {Promise<void>}
   */
  async function setRecipesOnly(next) {
    if (next === filters.recipesOnly) {
      return;
    }
    await apply({ ...filters, recipesOnly: next });
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
    panel.render(filters, filters.recipesOnly ? counts.recipes_only : counts.all_saves);
    renderSegmented();
    renderResults();
  }

  function renderSegmented() {
    setPressed(recipesSegment, filters.recipesOnly);
    setPressed(allSavesSegment, !filters.recipesOnly);
    allSavesSegment.textContent = `All saves \u00b7 ${counts.all_saves.toLocaleString()}`;
  }

  function renderResults() {
    grid.replaceChildren();
    rendered = 0;
    if (results.length === 0) {
      const empty = document.createElement("p");
      empty.className = "state-msg";
      empty.textContent = isNarrowed(filters)
        ? "No recipes match these filters."
        : "Nothing saved here yet.";
      grid.append(empty);
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
 * @param {string} label
 * @param {boolean} pressed
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function buildSegment(label, pressed, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "segmented__option";
  button.textContent = label;
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
