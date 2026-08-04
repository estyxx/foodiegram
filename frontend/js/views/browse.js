// @ts-check

import { getAllRecipes, updateRecipe } from "../api/client.js";
import { RecipeCard } from "../components/RecipeCard.js";

const PAGE_SIZE = 50;
const SEARCH_DEBOUNCE_MS = 200;

/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */
/** @typedef {import("../api/client.js").RecipeFilters} RecipeFilters */

/**
 * @typedef {object} CategoryChip
 * @property {string} value MedCategory value, or "" for the "All" reset chip.
 * @property {string} label
 * @property {string} [color] CSS custom-property name for the dot swatch.
 * @property {boolean} [ring] Render the dot as an outline (eggs, processed).
 */

/** The 7-category key, in Browse order (mirrors the domain MedCategory enum). */
const CATEGORY_CHIPS = /** @type {CategoryChip[]} */ ([
  { value: "", label: "All" },
  { value: "fish", label: "Fish", color: "--cat-fish" },
  { value: "legumes", label: "Legumes", color: "--cat-legumes" },
  { value: "poultry", label: "Poultry", color: "--cat-poultry" },
  { value: "eggs", label: "Eggs", color: "--cat-eggs", ring: true },
  { value: "dairy", label: "Dairy", color: "--cat-dairy" },
  { value: "red_meat", label: "Red meat", color: "--cat-red-meat" },
  { value: "processed_meat", label: "Processed", color: "--cat-processed", ring: true },
]);

/**
 * Render the browse (or favourites) view into container.
 * @param {HTMLElement} container
 * @param {{ favourites?: boolean }} [options]
 * @returns {Promise<void>}
 */
export async function renderBrowse(container, options) {
  const favourites = options?.favourites ?? false;
  container.replaceChildren();

  let query = "";
  let category = "";

  const chips = document.createElement("div");
  chips.className = "chip-filters";
  chips.setAttribute("role", "group");
  chips.setAttribute("aria-label", "Filter by Mediterranean category");

  const summary = document.createElement("p");
  summary.className = "browse__count";
  summary.setAttribute("aria-live", "polite");

  const grid = document.createElement("div");
  grid.className = "recipe-grid";

  const loadMore = document.createElement("div");
  loadMore.className = "load-more";
  const loadMoreButton = document.createElement("button");
  loadMoreButton.type = "button";
  loadMoreButton.className = "load-more__btn";
  loadMoreButton.addEventListener("click", renderMore);
  loadMore.append(loadMoreButton);

  const toolbar = buildToolbar((value) => {
    query = value;
    void refetch();
  });

  container.append(buildHero(favourites), toolbar, chips, summary, grid, loadMore);

  /** @type {RecipeSummary[]} Server results reflecting the current query. */
  let matched = [];
  /** @type {RecipeSummary[]} matched after category + sort. */
  let results = [];
  let rendered = 0;

  async function refetch() {
    matched = await getAllRecipes(toQuery(query, favourites));
    recompute();
  }

  function recompute() {
    results = filterByCategory(matched, category);
    renderChips();
    renderResults();
  }

  function renderChips() {
    chips.replaceChildren();
    for (const chip of CATEGORY_CHIPS) {
      chips.append(
        buildChip(chip, category === chip.value, () => {
          category = chip.value;
          recompute();
        }),
      );
    }
  }

  function renderResults() {
    grid.replaceChildren();
    rendered = 0;
    if (results.length === 0) {
      const empty = document.createElement("p");
      empty.className = "state-msg";
      empty.textContent = "No recipes match your filters.";
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
    matched = await getAllRecipes(toQuery(query, favourites));
    recompute();
  }

  matched = await getAllRecipes(toQuery(query, favourites));
  recompute();
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

/* ---- Toolbar: search + sort -------------------------------------------- */

/**
 * @param {(value: string) => void} onSearch
 * @returns {HTMLElement}
 */
function buildToolbar(onSearch) {
  const toolbar = document.createElement("div");
  toolbar.className = "browse__toolbar";
  toolbar.append(buildSearch(onSearch));
  return toolbar;
}

/**
 * @param {(value: string) => void} onInput
 * @returns {HTMLElement}
 */
function buildSearch(onInput) {
  const wrap = document.createElement("div");
  wrap.className = "searchbar";
  wrap.append(buildSearchIcon());

  const input = document.createElement("input");
  input.type = "search";
  input.className = "searchbar__input";
  input.placeholder = "Search recipes or ingredients\u2026";
  input.setAttribute("aria-label", "Search recipes or ingredients");

  let timer = 0;
  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => onInput(input.value.trim()), SEARCH_DEBOUNCE_MS);
  });
  wrap.append(input);
  return wrap;
}

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * @returns {SVGSVGElement}
 */
function buildSearchIcon() {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "searchbar__icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.6");
  svg.setAttribute("aria-hidden", "true");

  const circle = document.createElementNS(SVG_NS, "circle");
  circle.setAttribute("cx", "11");
  circle.setAttribute("cy", "11");
  circle.setAttribute("r", "7");

  const handle = document.createElementNS(SVG_NS, "line");
  handle.setAttribute("x1", "20");
  handle.setAttribute("y1", "20");
  handle.setAttribute("x2", "16.5");
  handle.setAttribute("y2", "16.5");
  handle.setAttribute("stroke-linecap", "round");

  svg.append(circle, handle);
  return svg;
}

/* ---- Category chips ----------------------------------------------------- */

/**
 * @param {CategoryChip} chip
 * @param {boolean} active
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function buildChip(chip, active, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "chip-filter";
  button.classList.toggle("chip-filter--active", active);
  button.setAttribute("aria-pressed", String(active));

  if (chip.color) {
    const dot = document.createElement("span");
    dot.className = chip.ring
      ? "chip-filter__dot chip-filter__dot--ring"
      : "chip-filter__dot";
    dot.style.setProperty("--dot", `var(${chip.color})`);
    dot.setAttribute("aria-hidden", "true");
    button.append(dot);
  }

  const text = document.createElement("span");
  text.textContent = chip.label;
  button.append(text);

  button.addEventListener("click", onClick);
  return button;
}

/* ---- Filtering / sorting ------------------------------------------------ */

/**
 * @param {RecipeSummary[]} recipes
 * @param {string} category
 * @returns {RecipeSummary[]}
 */
function filterByCategory(recipes, category) {
  if (!category) {
    return recipes;
  }
  return recipes.filter((recipe) =>
    recipe.mediterranean_categories.includes(category),
  );
}

/**
 * @param {string} query
 * @param {boolean} favourites
 * @returns {RecipeFilters}
 */
function toQuery(query, favourites) {
  /** @type {RecipeFilters} */
  const filters = {};
  if (query) {
    filters.q = query;
  }
  if (favourites) {
    filters.is_favorite = true;
  }
  return filters;
}
