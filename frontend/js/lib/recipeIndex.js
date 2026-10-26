// @ts-check

import { getRecipeIndex, updateRecipe } from "../api/client.js";

/** @typedef {import("../api/client.js").RecipeIndex} RecipeIndex */

/**
 * The slim recipe index, fetched once per session (D27). Recipes saved after
 * the page loaded (e.g. from Claude) appear on the next reload.
 * @type {Promise<RecipeIndex> | null}
 */
let loaded = null;

/**
 * Return the session's recipe index, fetching it on first use. A failed fetch
 * is not cached, so the next call retries.
 * @returns {Promise<RecipeIndex>}
 */
export function loadRecipeIndex() {
  if (loaded === null) {
    loaded = getRecipeIndex().catch((error) => {
      loaded = null;
      throw error;
    });
  }
  return loaded;
}

/**
 * Persist a favourite flag with one PATCH and mirror it into the cached index,
 * so no view has to refetch to see it.
 * @param {string} code
 * @param {boolean} isFavorite
 * @returns {Promise<boolean>} The stored flag.
 */
export async function setFavourite(code, isFavorite) {
  const updated = await updateRecipe(code, { is_favorite: isFavorite });
  if (loaded !== null) {
    const index = await loaded;
    const next = {
      ...index,
      recipes: index.recipes.map((entry) =>
        entry.code === code ? { ...entry, is_favorite: updated.is_favorite } : entry,
      ),
    };
    loaded = Promise.resolve(next);
  }
  return updated.is_favorite;
}
