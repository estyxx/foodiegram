// @ts-check

/**
 * Turn a snake_case or lowercase token into human-readable words.
 * @param {string} value
 * @returns {string}
 */
export function humanise(value) {
  return value.replace(/_/g, " ");
}

/**
 * The heading to show for a recipe that may have no title of its own.
 *
 * A fifth of the library was saved before extraction ran and has no title. The
 * account it came from is the most useful thing we can say instead — but it is
 * only ever said here, in the view. The stored title stays absent, so a later
 * extraction can tell a missing title from a guessed one.
 * @param {{ title: string | null, author_username: string | null }} recipe
 * @returns {string}
 */
export function displayTitle(recipe) {
  if (recipe.title !== null) {
    return recipe.title;
  }
  return recipe.author_username !== null
    ? `@${recipe.author_username}`
    : "Untitled save";
}

/**
 * Upper-case the first letter, leaving the rest alone.
 * @param {string} value
 * @returns {string}
 */
export function capitalise(value) {
  return value.length > 0 ? value[0].toUpperCase() + value.slice(1) : value;
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

const DAY_FORMATTER = new Intl.DateTimeFormat("it-IT", {
  weekday: "short",
  day: "numeric",
  month: "short",
});

/**
 * "lun 24 ago" for a day column heading.
 * @param {string} isoDate
 * @returns {string}
 */
export function formatDayLabel(isoDate) {
  return DAY_FORMATTER.format(new Date(`${isoDate}T00:00:00`));
}

const WEEK_RANGE_FORMATTER = new Intl.DateTimeFormat("it-IT", {
  day: "numeric",
  month: "short",
});

/**
 * "24 ago – 30 ago" for the plan header.
 * @param {string} weekStart ISO date (Monday).
 * @param {string} weekEnd ISO date (Sunday).
 * @returns {string}
 */
export function formatWeekRange(weekStart, weekEnd) {
  const start = WEEK_RANGE_FORMATTER.format(new Date(`${weekStart}T00:00:00`));
  const end = WEEK_RANGE_FORMATTER.format(new Date(`${weekEnd}T00:00:00`));
  return `${start} – ${end}`;
}
