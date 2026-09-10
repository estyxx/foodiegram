// @ts-check

import {
  proteinLabel,
  segmentCount,
  segmentLabel,
  selectLabel,
  widerThan,
} from "./facets.js";
import { capitalise, humanise } from "./format.js";

/** @typedef {import("../api/client.js").RecipeFilters} RecipeFilters */
/** @typedef {import("../api/client.js").RecipeCounts} RecipeCounts */

/**
 * Which slice of the library is on screen. The tiers nest: everything complete
 * is a recipe, and every recipe is a save.
 * @typedef {"complete" | "recipes" | "all"} Segment
 */

/**
 * Everything Browse narrows on, in one flat value. Never mutated: a change is
 * a new object, so the view can compare and refetch on identity alone.
 * @typedef {object} BrowseFilters
 * @property {string} query Free text, sent as `q`.
 * @property {string[]} ingredients Ingredient chips, AND-matched.
 * @property {string[]} proteins MedCategory values, OR-matched.
 * @property {string} dishType
 * @property {string} mealType
 * @property {string} cuisine
 * @property {string} difficulty
 * @property {string} dietaryTag
 * @property {Segment} segment
 */

/** The panel dropdowns, which all hold a single enum value or "" for Any. */
/** @typedef {"dishType" | "mealType" | "cuisine" | "difficulty" | "dietaryTag"} SelectKey */

/** @type {SelectKey[]} */
const SELECT_KEYS = ["dishType", "mealType", "cuisine", "difficulty", "dietaryTag"];

/** The resting state: recipes you can actually cook, nothing else narrowed. */
export function emptyFilters() {
  return /** @type {BrowseFilters} */ ({
    query: "",
    ingredients: [],
    proteins: [],
    dishType: "",
    mealType: "",
    cuisine: "",
    difficulty: "",
    dietaryTag: "",
    segment: "complete",
  });
}

/**
 * Drop everything the user narrowed by, keeping the segment they are viewing.
 * The segment is a view of the library, not a filter on it.
 * @param {BrowseFilters} filters
 * @returns {BrowseFilters}
 */
export function cleared(filters) {
  return { ...emptyFilters(), segment: filters.segment };
}

/**
 * Set one dropdown, where "" means Any.
 * @param {BrowseFilters} filters
 * @param {SelectKey} key
 * @param {string} value
 * @returns {BrowseFilters}
 */
export function withSelect(filters, key, value) {
  const next = { ...filters };
  next[key] = value;
  return next;
}

/**
 * Add or remove one protein category.
 * @param {BrowseFilters} filters
 * @param {string} category
 * @returns {BrowseFilters}
 */
export function withProteinToggled(filters, category) {
  const proteins = filters.proteins.includes(category)
    ? filters.proteins.filter((value) => value !== category)
    : [...filters.proteins, category];
  return { ...filters, proteins };
}

/**
 * Pin a search term as an ingredient chip, clearing the free text it came from.
 * Repeats are ignored, matched case-insensitively.
 * @param {BrowseFilters} filters
 * @param {string} term
 * @returns {BrowseFilters}
 */
export function withIngredient(filters, term) {
  const trimmed = term.trim();
  const known = filters.ingredients.some(
    (existing) => existing.toLowerCase() === trimmed.toLowerCase(),
  );
  if (trimmed === "" || known) {
    return { ...filters, query: "" };
  }
  return { ...filters, query: "", ingredients: [...filters.ingredients, trimmed] };
}

/**
 * @param {BrowseFilters} filters
 * @param {string} term
 * @returns {BrowseFilters}
 */
export function withoutIngredient(filters, term) {
  return {
    ...filters,
    ingredients: filters.ingredients.filter((existing) => existing !== term),
  };
}

/**
 * How many facets the Filters panel is holding. The ingredient chips are not
 * counted: they are already visible in the search line.
 * @param {BrowseFilters} filters
 * @returns {number}
 */
export function activeCount(filters) {
  const chosen = SELECT_KEYS.filter((key) => filters[key] !== "").length;
  return filters.proteins.length + chosen;
}

/**
 * True when the user has narrowed anything at all, panel or search line.
 * @param {BrowseFilters} filters
 * @returns {boolean}
 */
export function isNarrowed(filters) {
  return (
    activeCount(filters) > 0 || filters.ingredients.length > 0 || filters.query !== ""
  );
}

/**
 * One way out of an empty result set: what it undoes, and the filters it lands on.
 * @typedef {object} Relaxation
 * @property {string} label
 * @property {BrowseFilters} filters
 */

/**
 * The ways out of an empty result set, gentlest first.
 *
 * An empty grid should name what emptied it. Dropping one facet comes before
 * widening the tier, because losing a filter you chose costs less than being
 * moved to a slice of the library you did not ask for. Every way out leads
 * somewhere: a tier that is also empty under these facets is not offered.
 * @param {BrowseFilters} filters
 * @param {RecipeCounts} counts Totals for each tier under the current facets.
 * @returns {Relaxation[]}
 */
export function relaxations(filters, counts) {
  /** @type {Relaxation[]} */
  const ways = [];

  for (const key of SELECT_KEYS) {
    const value = filters[key];
    if (value !== "") {
      ways.push({
        label: `Remove ${selectLabel(key)}: ${capitalise(humanise(value))}`,
        filters: withSelect(filters, key, ""),
      });
    }
  }

  if (filters.proteins.length === 1) {
    ways.push({
      label: `Remove protein: ${proteinLabel(filters.proteins[0])}`,
      filters: { ...filters, proteins: [] },
    });
  } else if (filters.proteins.length > 1) {
    ways.push({
      label: `Remove ${filters.proteins.length} protein filters`,
      filters: { ...filters, proteins: [] },
    });
  }

  const wider = widerThan(filters.segment).find(
    (segment) => segmentCount(counts, segment) > 0,
  );
  if (wider !== undefined) {
    ways.push({
      label: `Widen to ${segmentLabel(wider)}`,
      filters: { ...filters, segment: wider },
    });
  }

  return ways;
}

/**
 * Translate the view's filters into API query parameters.
 * @param {BrowseFilters} filters
 * @param {{ favourites: boolean }} options
 * @returns {RecipeFilters}
 */
export function toQuery(filters, options) {
  /** @type {RecipeFilters} */
  const query = {};
  if (filters.query !== "") {
    query.q = filters.query;
  }
  if (filters.ingredients.length > 0) {
    query.ingredient = filters.ingredients;
  }
  if (filters.proteins.length > 0) {
    query.protein_category = filters.proteins;
  }
  if (filters.dishType !== "") {
    query.dish_type = filters.dishType;
  }
  if (filters.mealType !== "") {
    query.meal_type = filters.mealType;
  }
  if (filters.cuisine !== "") {
    query.cuisine = filters.cuisine;
  }
  if (filters.difficulty !== "") {
    query.difficulty = filters.difficulty;
  }
  if (filters.dietaryTag !== "") {
    query.dietary_tag = filters.dietaryTag;
  }
  // The tiers are compositions of two independent server filters; storage
  // knows nothing about "segments".
  if (filters.segment !== "all") {
    query.is_recipe = true;
  }
  if (filters.segment === "complete") {
    query.complete = true;
  }
  if (options.favourites) {
    query.is_favorite = true;
  }
  return query;
}
