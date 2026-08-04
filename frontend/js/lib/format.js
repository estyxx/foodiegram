// @ts-check

/**
 * Turn a snake_case or lowercase token into human-readable words.
 * @param {string} value
 * @returns {string}
 */
export function humanise(value) {
  return value.replace(/_/g, " ");
}

/** Enum members that carry no information and should not be shown as chips. */
const EMPTY_ENUMS = new Set(["", "unknown"]);

/**
 * Return true when an enum value is worth displaying to the user.
 * @param {string | null | undefined} value
 * @returns {value is string}
 */
export function hasValue(value) {
  return typeof value === "string" && !EMPTY_ENUMS.has(value);
}

/**
 * Format a serving count with at most one decimal place.
 * @param {number} servings
 * @returns {string}
 */
export function formatServings(servings) {
  return Number.isInteger(servings) ? String(servings) : servings.toFixed(1);
}

/**
 * Format a scaled ingredient quantity: round to 2 dp, drop trailing zeros.
 * @param {number} value
 * @returns {string}
 */
export function formatQuantity(value) {
  return String(Math.round(value * 100) / 100);
}
