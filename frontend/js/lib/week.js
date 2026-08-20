// @ts-check

/** @typedef {"lunch" | "dinner"} MealSlot */

/** Lunch and dinner, in display order — every day has exactly these two slots. */
export const MEAL_SLOTS = /** @type {readonly MealSlot[]} */ (["lunch", "dinner"]);

// Indexed by Date#getDay() (0=Sunday..6=Saturday): days to subtract to reach
// that week's Monday.
const MONDAY_OFFSETS = [-6, 0, -1, -2, -3, -4, -5];

/**
 * @param {Date} date
 * @returns {string} ISO date (YYYY-MM-DD), in local time.
 */
export function isoDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * Shift an ISO date by a number of days (may be negative).
 * @param {string} iso
 * @param {number} deltaDays
 * @returns {string}
 */
export function addDays(iso, deltaDays) {
  const date = new Date(`${iso}T00:00:00`);
  date.setDate(date.getDate() + deltaDays);
  return isoDate(date);
}

/**
 * The ISO date of the Monday starting the week containing `date` (week_plans
 * are Monday-anchored — see WeekPlan._must_be_monday).
 * @param {Date} date
 * @returns {string}
 */
export function mondayOf(date) {
  // getDay(): 0=Sunday..6=Saturday; Monday needs its own offset since it is
  // not day 0.
  const offset = MONDAY_OFFSETS[date.getDay()];
  return addDays(isoDate(date), offset);
}

/**
 * The 7 ISO dates of the week starting at weekStart (Monday..Sunday).
 * @param {string} weekStart
 * @returns {string[]}
 */
export function weekDays(weekStart) {
  return Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));
}
