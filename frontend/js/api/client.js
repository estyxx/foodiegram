// @ts-check

/**
 * @typedef {object} RecipeSummary
 * @property {string} code
 * @property {string} title
 * @property {string} cuisine_type
 * @property {string} meal_type
 * @property {string} dish_type
 * @property {string} difficulty
 * @property {string[]} dietary_tags
 * @property {string[]} proteins
 * @property {string | null} thumbnail_url
 * @property {string | null} cloudinary_url
 * @property {boolean} is_favorite
 * @property {boolean} has_instructions
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
 * @property {string} title
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
 * @property {boolean} edited_by_user
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
 * @property {boolean} [is_favorite]
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
 * List recipes matching the given filters.
 * @param {RecipeFilters} [filters]
 * @returns {Promise<RecipeSummary[]>}
 */
export async function getRecipes(filters) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters ?? {})) {
    if (value !== "" && value !== undefined && value !== null) {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  const result = await apiFetch(query ? `/recipes?${query}` : "/recipes");
  return /** @type {RecipeSummary[]} */ (result);
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
