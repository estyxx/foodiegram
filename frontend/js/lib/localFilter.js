// @ts-check

/** @typedef {import("../api/client.js").RecipeIndex} RecipeIndex */
/** @typedef {import("../api/client.js").RecipeIndexEntry} RecipeIndexEntry */
/** @typedef {import("../api/client.js").RecipeCounts} RecipeCounts */
/** @typedef {import("./filters.js").BrowseFilters} BrowseFilters */

/**
 * @typedef {object} LocalSearch
 * @property {RecipeIndexEntry[]} results Entries in the current segment, in index order.
 * @property {RecipeCounts} counts All three segment totals under the facets.
 */

/** @type {WeakMap<string[][], Map<string, string[]>>} */
const lookups = new WeakMap();

/**
 * term (lowercased) → its whole synonym group, built once per index.
 * @param {string[][]} synonyms
 * @returns {Map<string, string[]>}
 */
function synonymLookup(synonyms) {
  let lookup = lookups.get(synonyms);
  if (lookup === undefined) {
    lookup = new Map();
    for (const group of synonyms) {
      for (const term of group) {
        lookup.set(term, group);
      }
    }
    lookups.set(synonyms, lookup);
  }
  return lookup;
}

/**
 * The term and its synonyms, lowercased — the server's expand_term.
 * @param {string} term
 * @param {Map<string, string[]>} lookup
 * @returns {string[]}
 */
function expand(term, lookup) {
  const lower = term.toLowerCase();
  return lookup.get(lower) ?? [lower];
}

/**
 * True when any form of term appears in the entry's search text — the
 * server's _matches_term over title, ingredient lines and caption.
 * @param {RecipeIndexEntry} entry
 * @param {string} term
 * @param {Map<string, string[]>} lookup
 * @returns {boolean}
 */
function mentions(entry, term, lookup) {
  return expand(term, lookup).some((needle) => entry.search_text.includes(needle));
}

/**
 * Every non-segment filter, mirroring RecipeRepository.find: scalar facets are
 * equality, protein categories OR over the server-computed facets, the dietary
 * tag matches through synonyms, ingredient chips AND, and free text matches
 * like a chip.
 * @param {RecipeIndexEntry} entry
 * @param {BrowseFilters} filters
 * @param {Map<string, string[]>} lookup
 * @returns {boolean}
 */
function matchesFacets(entry, filters, lookup) {
  if (filters.cuisine !== "" && entry.cuisine_type !== filters.cuisine) {
    return false;
  }
  if (filters.mealType !== "" && entry.meal_type !== filters.mealType) {
    return false;
  }
  if (filters.dishType !== "" && entry.dish_type !== filters.dishType) {
    return false;
  }
  if (filters.difficulty !== "" && entry.difficulty !== filters.difficulty) {
    return false;
  }
  if (
    filters.proteins.length > 0 &&
    !filters.proteins.some((category) => entry.facets.includes(category))
  ) {
    return false;
  }
  if (filters.dietaryTag !== "") {
    const wanted = expand(filters.dietaryTag, lookup);
    const tags = entry.dietary_tags.map((tag) => tag.toLowerCase());
    if (!wanted.some((tag) => tags.includes(tag))) {
      return false;
    }
  }
  if (!filters.ingredients.every((term) => mentions(entry, term, lookup))) {
    return false;
  }
  return filters.query === "" || mentions(entry, filters.query, lookup);
}

/**
 * Filter and count the index locally: the results for the current segment and
 * every segment's total, like GET /recipes plus GET /recipes/count.
 * @param {RecipeIndex} index
 * @param {BrowseFilters} filters
 * @param {{ favourites: boolean }} options
 * @returns {LocalSearch}
 */
export function searchLocally(index, filters, options) {
  const lookup = synonymLookup(index.synonyms);
  const matched = index.recipes.filter(
    (entry) =>
      (!options.favourites || entry.is_favorite) &&
      matchesFacets(entry, filters, lookup),
  );
  const recipes = matched.filter((entry) => entry.is_recipe);
  const complete = recipes.filter((entry) => entry.is_complete);
  const bySegment = { all: matched, recipes, complete };
  return {
    results: bySegment[filters.segment],
    counts: {
      complete: complete.length,
      recipes: recipes.length,
      all_saves: matched.length,
    },
  };
}
