// @ts-check

/**
 * @typedef {object} RecipeSummary
 * @property {string} code
 * @property {string | null} title Absent on saves that were never extracted.
 * @property {string | null} description
 * @property {string | null} author_username
 * @property {string} cuisine_type
 * @property {string} meal_type
 * @property {string} dish_type
 * @property {string} difficulty
 * @property {string | null} total_time
 * @property {number | null} base_servings
 * @property {string[]} dietary_tags
 * @property {string[]} proteins
 * @property {string[]} mediterranean_categories
 * @property {string | null} thumbnail_url
 * @property {string | null} cloudinary_url
 * @property {boolean} is_favorite
 * @property {boolean} has_ingredients
 * @property {boolean} has_instructions
 * @property {number | null} [score] Similarity rank; only set by semantic search.
 */

/**
 * A slim recipe plus the server-derived fields Browse filters on locally (D27).
 * @typedef {RecipeSummary & {
 *   is_recipe: boolean,
 *   is_complete: boolean,
 *   facets: string[],
 *   search_text: string,
 * }} RecipeIndexEntry
 */

/**
 * @typedef {object} RecipeIndex
 * @property {RecipeIndexEntry[]} recipes Ordered by code, like GET /recipes.
 * @property {string[][]} synonyms Lowercased cross-language synonym groups.
 */

/**
 * @typedef {object} MedCategory
 * @property {string} category
 * @property {number} servings
 * @property {boolean} is_oily_fish
 */

/**
 * @typedef {object} RecipeDetail
 * @property {string} code
 * @property {"instagram" | "manual"} source
 * @property {string | null} author_username
 * @property {string} summary "" when the extractor wrote none
 * @property {string | null} title
 * @property {string[]} ingredients
 * @property {string[]} instructions
 * @property {string} cuisine_type
 * @property {string} meal_type
 * @property {string} dish_type
 * @property {string} difficulty
 * @property {string} course
 * @property {string[]} dietary_tags
 * @property {string[]} health_tags
 * @property {string[]} proteins
 * @property {string[]} vegetables
 * @property {string[]} grains_starches
 * @property {string[]} herbs_spices
 * @property {string[]} cooking_methods
 * @property {string[]} equipment
 * @property {MedCategory[]} mediterranean_categories
 * @property {string | null} prep_time
 * @property {string | null} cook_time
 * @property {number | null} base_servings
 * @property {string | null} thumbnail_url
 * @property {string | null} cloudinary_url
 * @property {string | null} skill_level
 * @property {string[]} edited_fields
 * @property {boolean} is_favorite
 * @property {string | null} user_notes
 */

/**
 * @typedef {object} VersionInfo
 * @property {string} version
 * @property {string} commit
 */

/**
 * @typedef {object} RecipeFilters
 * @property {string} [q]
 * @property {string} [cuisine]
 * @property {string} [meal_type]
 * @property {string} [dish_type]
 * @property {string} [difficulty]
 * @property {string} [dietary_tag]
 * @property {string} [protein]
 * @property {string[]} [protein_category] Repeatable; OR-matched by the server.
 * @property {string[]} [ingredient] Repeatable; AND-matched by the server.
 * @property {boolean} [is_recipe]
 * @property {boolean} [complete] Has both ingredients and a method.
 * @property {boolean} [is_favorite]
 */

/**
 * Segment totals, nested widest last: complete ⊆ recipes ⊆ all_saves.
 * @typedef {object} RecipeCounts
 * @property {number} complete
 * @property {number} recipes
 * @property {number} all_saves
 */

/**
 * @typedef {object} PlannedMeal
 * @property {number | null} id Null until the server assigns one.
 * @property {string} day ISO date.
 * @property {"lunch" | "dinner"} meal
 * @property {string} recipe_code
 * @property {number} portions
 */

/**
 * @typedef {object} CategoryStatus
 * @property {string} category
 * @property {number} planned
 * @property {number} min_servings
 * @property {number} max_servings
 * @property {"under" | "ok" | "over"} state
 */

/**
 * @typedef {object} GapSuggestion
 * @property {string} category
 * @property {RecipeSummary[]} recipes
 */

/**
 * Plan + balance + suggestions in one payload; the FE does no balance math.
 * @typedef {object} PlanResponse
 * @property {string} week_start ISO date (a Monday).
 * @property {PlannedMeal[]} meals
 * @property {CategoryStatus[]} balance
 * @property {number} oily_fish
 * @property {GapSuggestion[]} suggestions
 */

const API_BASE = "/api";

/**
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<unknown>}
 */
async function apiFetch(path, options) {
  const res = await fetch(API_BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${path}`);
  }
  return res.json();
}

/**
 * Serialise filters into query parameters, dropping empty values.
 * Array values repeat the key, which is how the API reads multi-value facets.
 * @param {RecipeFilters} [filters]
 * @returns {URLSearchParams}
 */
function toParams(filters) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, item);
      }
    } else if (value !== "" && value !== undefined && value !== null) {
      params.set(key, String(value));
    }
  }
  return params;
}

/**
 * List recipes matching the given filters, optionally paginated.
 * @param {RecipeFilters} [filters]
 * @param {{ limit?: number, offset?: number }} [page]
 * @returns {Promise<RecipeSummary[]>}
 */
export async function getRecipes(filters, page) {
  const params = toParams(filters);
  if (page?.limit !== undefined) {
    params.set("limit", String(page.limit));
  }
  if (page?.offset !== undefined) {
    params.set("offset", String(page.offset));
  }
  const query = params.toString();
  const result = await apiFetch(query ? `/recipes?${query}` : "/recipes");
  return /** @type {RecipeSummary[]} */ (result);
}

/**
 * Rank recipes by meaning against `filters.q`, under the same facets as getRecipes.
 * Returns [] for an empty query without making a request.
 * @param {RecipeFilters} [filters]
 * @param {number} [limit]
 * @returns {Promise<RecipeSummary[]>}
 */
export async function searchRecipesSemantic(filters, limit) {
  if (!filters?.q || filters.q.trim() === "") {
    return [];
  }
  const params = toParams(filters);
  if (limit !== undefined) {
    params.set("limit", String(limit));
  }
  const result = await apiFetch(`/recipes/semantic?${params.toString()}`);
  return /** @type {RecipeSummary[]} */ (result);
}

/**
 * Fetch every recipe's slim index entry and the synonym groups in one call.
 * Callers should go through lib/recipeIndex.js, which fetches once per session.
 * @returns {Promise<RecipeIndex>}
 */
export async function getRecipeIndex() {
  const result = await apiFetch("/recipes/index");
  return /** @type {RecipeIndex} */ (result);
}

/**
 * Fetch a single recipe by shortcode.
 * @param {string} code
 * @returns {Promise<RecipeDetail>}
 */
export async function getRecipe(code) {
  const result = await apiFetch(`/recipes/${encodeURIComponent(code)}`);
  return /** @type {RecipeDetail} */ (result);
}

/**
 * Fetch the deployed application version and source commit.
 * @returns {Promise<VersionInfo>}
 */
export async function getVersion() {
  const result = await apiFetch("/version");
  return /** @type {VersionInfo} */ (result);
}

/**
 * Fetch a week's plan, balance, and gap suggestions in one payload.
 * @param {string} weekStart ISO date (must be a Monday).
 * @returns {Promise<PlanResponse>}
 */
export async function getPlan(weekStart) {
  const result = await apiFetch(`/plans/${weekStart}`);
  return /** @type {PlanResponse} */ (result);
}

/**
 * @typedef {object} MealCreateBody
 * @property {string} day ISO date.
 * @property {"lunch" | "dinner"} meal
 * @property {string} recipe_code
 * @property {number} [portions]
 */

/**
 * Add a dish to a (day, meal) slot beside any already there (D34). Adding a
 * recipe the slot already holds only updates its portions.
 * @param {string} weekStart
 * @param {MealCreateBody} meal
 * @returns {Promise<PlanResponse>}
 */
export async function addMeal(weekStart, meal) {
  const result = await apiFetch(`/plans/${weekStart}/meals`, {
    method: "POST",
    body: JSON.stringify(meal),
  });
  return /** @type {PlanResponse} */ (result);
}

/**
 * @typedef {object} MealUpdateBody
 * @property {string} recipe_code
 * @property {number} [portions]
 */

/**
 * Swap the recipe or portions of one planned dish, by its id.
 * @param {string} weekStart
 * @param {number} mealId
 * @param {MealUpdateBody} meal
 * @returns {Promise<PlanResponse>}
 */
export async function updateMeal(weekStart, mealId, meal) {
  const result = await apiFetch(`/plans/${weekStart}/meals/${mealId}`, {
    method: "PUT",
    body: JSON.stringify(meal),
  });
  return /** @type {PlanResponse} */ (result);
}

/**
 * Remove one planned dish from the plan.
 * @param {string} weekStart
 * @param {number} mealId
 * @returns {Promise<PlanResponse>}
 */
export async function deleteMeal(weekStart, mealId) {
  const result = await apiFetch(`/plans/${weekStart}/meals/${mealId}`, {
    method: "DELETE",
  });
  return /** @type {PlanResponse} */ (result);
}

/**
 * A hand-written recipe (D23), saved as source=manual. `inspired_by` lists the
 * codes of the saves it is a version of.
 * @typedef {object} RecipeDraft
 * @property {string} title
 * @property {string[]} ingredients
 * @property {string[]} instructions
 * @property {MedCategory[]} mediterranean_categories
 * @property {string[]} inspired_by
 */

/**
 * Save a hand-written recipe and return it as stored, with its new code.
 * @param {RecipeDraft} draft
 * @returns {Promise<RecipeDetail>}
 */
export async function createRecipe(draft) {
  const result = await apiFetch("/recipes", {
    method: "POST",
    body: JSON.stringify(draft),
  });
  return /** @type {RecipeDetail} */ (result);
}

/**
 * Apply a partial update (favourite, notes, servings) to a recipe.
 * @param {string} code
 * @param {Partial<Pick<RecipeDetail, "is_favorite" | "user_notes" | "base_servings">>} patch
 * @returns {Promise<RecipeDetail>}
 */
export async function updateRecipe(code, patch) {
  const result = await apiFetch(`/recipes/${encodeURIComponent(code)}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return /** @type {RecipeDetail} */ (result);
}
