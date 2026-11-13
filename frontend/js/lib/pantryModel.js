// @ts-check

/** @typedef {import("../api/client.js").PantryItem} PantryItem */

/** Locations in shopping order, with their display label. */
export const LOCATIONS = /** @type {const} */ ([
  ["fridge", "Fridge"],
  ["pantry", "Pantry"],
  ["freezer", "Freezer"],
  ["unknown", "Other"],
]);

const MS_PER_DAY = 86400000;
/** A date only earns a badge inside its last week. */
const SOON_WINDOW = 7;

/**
 * @param {string} value
 * @returns {string}
 */
export function locationLabel(value) {
  const found = LOCATIONS.find(([key]) => key === value);
  return found ? found[1] : "Other";
}

/**
 * Midnight of the given day, so date maths ignores the time of day.
 * @param {Date} date
 * @returns {Date}
 */
export function startOfDay(date) {
  const copy = new Date(date.getTime());
  copy.setHours(0, 0, 0, 0);
  return copy;
}

/**
 * @param {Date} today
 * @param {number} offset
 * @returns {string}
 */
export function isoOffset(today, offset) {
  const day = startOfDay(today);
  day.setDate(day.getDate() + offset);
  const pad = (/** @type {number} */ n) => String(n).padStart(2, "0");
  return `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;
}

/**
 * Whole days from today to an ISO date, or null when there is no valid date.
 * @param {string | null} expires
 * @param {Date} today
 * @returns {number | null}
 */
export function daysToExpiry(expires, today) {
  if (!expires) {
    return null;
  }
  const due = new Date(`${expires}T00:00:00`);
  if (Number.isNaN(due.getTime())) {
    return null;
  }
  return Math.round((due.getTime() - startOfDay(today).getTime()) / MS_PER_DAY);
}

/**
 * @param {string} expires
 * @returns {string}
 */
function shortDate(expires) {
  const due = new Date(`${expires}T00:00:00`);
  return due.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/**
 * @typedef {object} ExpiryStatus
 * @property {"soon" | "expired"} kind
 * @property {string} short Badge label.
 * @property {string} long Use-soon row label.
 * @property {number} days
 */

/**
 * Expiry state, or null when the item needs no badge (undated or far off).
 * @param {string | null} expires
 * @param {Date} today
 * @returns {ExpiryStatus | null}
 */
export function expiryStatus(expires, today) {
  const days = daysToExpiry(expires, today);
  if (days === null || days > SOON_WINDOW) {
    return null;
  }
  if (days < 0 && expires !== null) {
    return { kind: "expired", short: "Expired", long: `Expired ${shortDate(expires)}`, days };
  }
  if (days === 0) {
    return { kind: "soon", short: "Use today", long: "Use today", days };
  }
  if (days === 1) {
    return { kind: "soon", short: "Tomorrow", long: "Tomorrow", days };
  }
  return { kind: "soon", short: `${days} days`, long: `${days} days`, days };
}

/**
 * A human sentence under the date input while editing.
 * @param {string | null} expires
 * @param {Date} today
 * @returns {string}
 */
export function expiryNote(expires, today) {
  const days = daysToExpiry(expires, today);
  if (days === null) {
    return "No date set. It will never show a badge.";
  }
  let relative;
  if (days < 0) {
    relative = `expired ${-days} ${-days === 1 ? "day" : "days"} ago`;
  } else if (days === 0) {
    relative = "today";
  } else if (days === 1) {
    relative = "tomorrow";
  } else {
    relative = `in ${days} days`;
  }
  const tail = days > SOON_WINDOW ? " · no badge until the last week" : "";
  return `${shortDate(expires ?? "")} · ${relative}${tail}`;
}

/**
 * Sort items by name, Italian collation, accents and case folded.
 * @param {PantryItem} a
 * @param {PantryItem} b
 * @returns {number}
 */
export function byName(a, b) {
  return a.name.localeCompare(b.name, "it", { sensitivity: "base" });
}

/**
 * @typedef {object} PantrySection
 * @property {string} key
 * @property {string} label
 * @property {PantryItem[]} items
 * @property {number} soonCount
 */

/**
 * Group items into non-empty location sections, each sorted A–Z.
 * @param {PantryItem[]} items
 * @param {Date} today
 * @returns {PantrySection[]}
 */
export function sections(items, today) {
  return LOCATIONS.map(([key, label]) => {
    const inLocation = items.filter((item) => item.location === key).sort(byName);
    const soonCount = inLocation.filter((item) => expiryStatus(item.expires, today) !== null)
      .length;
    return { key, label, items: inLocation, soonCount };
  }).filter((section) => section.items.length > 0);
}

/**
 * @typedef {object} UseSoon
 * @property {PantryItem[]} soon
 * @property {PantryItem[]} expired
 */

/**
 * The two "use soon" buckets: soonest first, then expired most-overdue first.
 * @param {PantryItem[]} items
 * @param {Date} today
 * @returns {UseSoon}
 */
export function useSoon(items, today) {
  const rated = items.map((item) => ({ item, status: expiryStatus(item.expires, today) }));
  const soon = rated
    .filter((entry) => entry.status?.kind === "soon")
    .sort((a, b) => (a.status?.days ?? 0) - (b.status?.days ?? 0) || byName(a.item, b.item))
    .map((entry) => entry.item);
  const expired = rated
    .filter((entry) => entry.status?.kind === "expired")
    .sort((a, b) => (a.status?.days ?? 0) - (b.status?.days ?? 0))
    .map((entry) => entry.item);
  return { soon, expired };
}

/**
 * The one-line summary under the title.
 * @param {PantryItem[]} items
 * @param {Date} today
 * @returns {string}
 */
export function summaryLine(items, today) {
  const total = items.length;
  if (total === 0) {
    return "Nothing on the shelves yet.";
  }
  const soon = useSoon(items, today).soon.length;
  const things = `${total} ${total === 1 ? "thing" : "things"} on hand`;
  return soon > 0 ? `${things} · ${soon} to use soon.` : `${things}.`;
}
