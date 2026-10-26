// @ts-check

import { getRecipeIndex, updateRecipe } from "../api/client.js";

/** @typedef {import("../api/client.js").RecipeIndex} RecipeIndex */
/** @typedef {import("../api/client.js").RecipeIndexEntry} RecipeIndexEntry */

/**
 * The slim recipe index, fetched once per session (D27). Recipes saved after
 * the page loaded (e.g. from Claude) appear on the next reload.
 * @type {Promise<RecipeIndex> | null}
 */
let loaded = null;

/**
 * The same index once it has arrived, for synchronous peeks.
 * @type {RecipeIndex | null}
 */
let current = null;

/** @type {WeakMap<RecipeIndex, Map<string, RecipeIndexEntry>>} */
const byCode = new WeakMap();

/**
 * Return the session's recipe index, fetching it on first use. A failed fetch
 * is not cached, so the next call retries.
 * @returns {Promise<RecipeIndex>}
 */
export function loadRecipeIndex() {
  if (loaded === null) {
    loaded = getRecipeIndex().then(
      (index) => {
        current = index;
        return index;
      },
      (error) => {
        loaded = null;
        throw error;
      },
    );
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
    current = next;
    loaded = Promise.resolve(next);
  }
  return updated.is_favorite;
}

/**
 * The index if this session has already loaded it, else null. Never fetches:
 * a shared /#recipe link opened without a password must not ask for the
 * (private) index.
 * @returns {RecipeIndex | null}
 */
export function peekRecipeIndex() {
  return current;
}

/**
 * Look a recipe up in an index by code.
 * @param {RecipeIndex} index
 * @param {string} code
 * @returns {RecipeIndexEntry | undefined}
 */
export function indexedRecipe(index, code) {
  let lookup = byCode.get(index);
  if (lookup === undefined) {
    lookup = new Map(index.recipes.map((entry) => [entry.code, entry]));
    byCode.set(index, lookup);
  }
  return lookup.get(code);
}
