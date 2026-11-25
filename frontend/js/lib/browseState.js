// @ts-check

import { SEGMENTS } from "./facets.js";
import { emptyFilters } from "./filters.js";

/** @typedef {import("./filters.js").BrowseFilters} BrowseFilters */

/**
 * Where Browse was, so coming back from a recipe lands on the same search.
 * @typedef {object} BrowseState
 * @property {BrowseFilters} filters
 * @property {"lexical" | "ai"} mode
 * @property {number} shown how many cards were on screen
 * @property {number} scrollY
 */

const KEY_PREFIX = "dispensa.browse.";

/**
 * @param {unknown} value
 * @returns {value is string[]}
 */
function isStringList(value) {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

/**
 * Read a saved state back, keeping only well-formed fields: anything missing or
 * of the wrong type falls back to a fresh Browse, never to a broken one.
 * @param {string | null} raw
 * @returns {BrowseState | null}
 */
export function parseBrowseState(raw) {
  if (!raw) {
    return null;
  }
  /** @type {unknown} */
  let data;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null) {
    return null;
  }
  const record = /** @type {Record<string, unknown>} */ (data);
  const saved = /** @type {Record<string, unknown>} */ (
    typeof record.filters === "object" && record.filters !== null ? record.filters : {}
  );
  const filters = emptyFilters();
  for (const key of /** @type {(keyof BrowseFilters)[]} */ (Object.keys(filters))) {
    const value = saved[key];
    const fresh = filters[key];
    if (Array.isArray(fresh) ? isStringList(value) : typeof value === "string") {
      Object.assign(filters, { [key]: value });
    }
  }
  if (!SEGMENTS.some((segment) => segment.value === filters.segment)) {
    filters.segment = emptyFilters().segment;
  }
  return {
    filters,
    mode: record.mode === "ai" ? "ai" : "lexical",
    shown: Number.isFinite(record.shown) ? Math.max(0, Number(record.shown)) : 0,
    scrollY: Number.isFinite(record.scrollY) ? Math.max(0, Number(record.scrollY)) : 0,
  };
}

/**
 * The saved state for one Browse tab ("browse" or "favourites"), or null.
 * @param {string} tab
 * @returns {BrowseState | null}
 */
export function loadBrowseState(tab) {
  try {
    return parseBrowseState(window.sessionStorage.getItem(KEY_PREFIX + tab));
  } catch {
    return null;
  }
}

/**
 * Remember Browse's state for this tab, for the rest of the session.
 * @param {string} tab
 * @param {BrowseState} state
 */
export function saveBrowseState(tab, state) {
  try {
    window.sessionStorage.setItem(KEY_PREFIX + tab, JSON.stringify(state));
  } catch {
    // Storage blocked: Browse still works, it just starts fresh next time.
  }
}
