// @ts-check

import { getRecipes, updateRecipe } from "../api/client.js";
import { RecipeCard } from "../components/RecipeCard.js";
import { humanise } from "../lib/format.js";

/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */
/** @typedef {import("../api/client.js").RecipeFilters} RecipeFilters */

/**
 * @typedef {object} FilterGroup
 * @property {"cuisine" | "meal_type" | "difficulty" | "dietary_tag"} key
 * @property {string} label
 * @property {(recipe: RecipeSummary) => string[]} values
 */

/** @type {FilterGroup[]} */
const FILTER_GROUPS = [
  { key: "cuisine", label: "Cuisine", values: (r) => single(r.cuisine_type) },
  { key: "meal_type", label: "Meal", values: (r) => single(r.meal_type) },
  { key: "difficulty", label: "Difficulty", values: (r) => single(r.difficulty) },
  { key: "dietary_tag", label: "Dietary", values: (r) => r.dietary_tags },
];

/**
 * @param {string} value
 * @returns {string[]}
 */
function single(value) {
  return value && value !== "unknown" ? [value] : [];
}

/**
 * @typedef {object} FilterState
 * @property {string} q
 * @property {string} cuisine
 * @property {string} meal_type
 * @property {string} difficulty
 * @property {string} dietary_tag
 */

/**
 * Render the browse (or favourites) view into container.
 * @param {HTMLElement} container
 * @param {{ favourites?: boolean }} [options]
 * @returns {Promise<void>}
 */
export async function renderBrowse(container, options) {
  const favourites = options?.favourites ?? false;
  /** @type {FilterState} */
  const filters = {
    q: "",
    cuisine: "",
    meal_type: "",
    difficulty: "",
    dietary_tag: "",
  };

  container.replaceChildren();

  const heading = document.createElement("h1");
  heading.className = "browse__title";
  heading.textContent = favourites ? "Favourites" : "Browse recipes";

  const search = buildSearch(() => refetch());
  const filtersEl = document.createElement("div");
  filtersEl.className = "filters";

  const header = document.createElement("div");
  header.className = "browse__header";
  header.append(heading, search, filtersEl);

  const summary = document.createElement("p");
  summary.className = "browse__summary";
  summary.setAttribute("aria-live", "polite");

  const grid = document.createElement("div");
  grid.className = "recipe-grid";

  container.append(header, summary, grid);

  /** @type {RecipeSummary[]} */
  let universe = [];

  async function refetch() {
    filters.q = search.value.trim();
    const recipes = await getRecipes(toQuery(filters, favourites));
    renderResults(recipes);
  }

  /**
   * @param {RecipeSummary[]} recipes
   */
  function renderResults(recipes) {
    summary.textContent = `${recipes.length} ${
      recipes.length === 1 ? "recipe" : "recipes"
    }`;
    grid.replaceChildren();
    if (recipes.length === 0) {
      const empty = document.createElement("p");
      empty.className = "state-msg";
      empty.textContent = "No recipes match your filters.";
      grid.append(empty);
      return;
    }
    for (const recipe of recipes) {
      grid.append(RecipeCard(recipe, { onToggleFavourite }));
    }
  }

  /**
   * @param {RecipeSummary} recipe
   */
  async function onToggleFavourite(recipe) {
    await updateRecipe(recipe.code, { is_favorite: !recipe.is_favorite });
    await refetch();
  }

  function renderFilters() {
    filtersEl.replaceChildren();
    for (const group of FILTER_GROUPS) {
      const values = collect(universe, group);
      if (values.length === 0) {
        continue;
      }
      filtersEl.append(buildFilterGroup(group, values, filters, refetch));
    }
    if (hasActiveFilter(filters)) {
      filtersEl.append(buildClearButton(filters, search, refetch));
    }
  }

  universe = await getRecipes(favourites ? { is_favorite: true } : {});
  renderFilters();
  renderResults(universe);
}

/**
 * @param {() => void} onInput
 * @returns {HTMLInputElement}
 */
function buildSearch(onInput) {
  const input = document.createElement("input");
  input.type = "search";
  input.className = "search";
  input.placeholder = "Search recipes\u2026";
  input.setAttribute("aria-label", "Search recipes");
  let timer = 0;
  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(onInput, 200);
  });
  return input;
}

/**
 * @param {FilterGroup} group
 * @param {string[]} values
 * @param {FilterState} filters
 * @param {() => void} onChange
 * @returns {HTMLElement}
 */
function buildFilterGroup(group, values, filters, onChange) {
  const wrap = document.createElement("div");
  wrap.className = "filter-group";
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", group.label);

  const label = document.createElement("span");
  label.className = "filter-group__label";
  label.textContent = group.label;
  wrap.append(label);

  for (const value of values) {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "pill";
    pill.textContent = humanise(value);
    const active = filters[group.key] === value;
    pill.classList.toggle("pill--active", active);
    pill.setAttribute("aria-pressed", String(active));
    pill.addEventListener("click", () => {
      filters[group.key] = filters[group.key] === value ? "" : value;
      onChange();
    });
    wrap.append(pill);
  }
  return wrap;
}

/**
 * @param {FilterState} filters
 * @param {HTMLInputElement} search
 * @param {() => void} onChange
 * @returns {HTMLButtonElement}
 */
function buildClearButton(filters, search, onChange) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "filters__clear";
  button.textContent = "Clear filters";
  button.addEventListener("click", () => {
    filters.cuisine = "";
    filters.meal_type = "";
    filters.difficulty = "";
    filters.dietary_tag = "";
    filters.q = "";
    search.value = "";
    onChange();
  });
  return button;
}

/**
 * @param {RecipeSummary[]} universe
 * @param {FilterGroup} group
 * @returns {string[]}
 */
function collect(universe, group) {
  /** @type {Set<string>} */
  const set = new Set();
  for (const recipe of universe) {
    for (const value of group.values(recipe)) {
      set.add(value);
    }
  }
  return [...set].sort();
}

/**
 * @param {FilterState} filters
 * @returns {boolean}
 */
function hasActiveFilter(filters) {
  return Boolean(
    filters.cuisine ||
      filters.meal_type ||
      filters.difficulty ||
      filters.dietary_tag ||
      filters.q,
  );
}

/**
 * @param {FilterState} filters
 * @param {boolean} favourites
 * @returns {RecipeFilters}
 */
function toQuery(filters, favourites) {
  /** @type {RecipeFilters} */
  const query = {};
  if (filters.q) query.q = filters.q;
  if (filters.cuisine) query.cuisine = filters.cuisine;
  if (filters.meal_type) query.meal_type = filters.meal_type;
  if (filters.difficulty) query.difficulty = filters.difficulty;
  if (filters.dietary_tag) query.dietary_tag = filters.dietary_tag;
  if (favourites) query.is_favorite = true;
  return query;
}
