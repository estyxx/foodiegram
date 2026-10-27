// @ts-check

/**
 * @typedef {object} StepTime
 * @property {number} seconds
 * @property {string} label e.g. "3 min" or "12–14 min"
 */
/**
 * A run of step text; `time` is set when the run is a detected duration.
 * @typedef {{ text: string, time: StepTime | null }} StepSegment
 */
/**
 * @typedef {object} ParsedStep
 * @property {string | null} title the "Soffritto:" lead-in, when the step has one
 * @property {string} body
 * @property {StepSegment[]} segments
 * @property {StepTime[]} times unique by duration, in reading order
 * @property {string} short title, or "Step n" — names the step's timers
 */

/**
 * Number words written out in captions (English and Italian). No "a"/"un":
 * "è un minuto in più del pacco" is a remark, not a timer.
 */
const NUMBER_WORDS = /** @type {Record<string, number>} */ ({
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8,
  nine: 9, ten: 10, twelve: 12, fifteen: 15, twenty: 20, thirty: 30, forty: 40,
  uno: 1, due: 2, tre: 3, quattro: 4, cinque: 5, sei: 6, sette: 7, otto: 8,
  nove: 9, dieci: 10, quindici: 15, venti: 20, trenta: 30,
});

const NUMBER = "\\d+(?:[.,]\\d+)?";
const UNIT =
  "minutes?|mins?|minut[oi]|seconds?|secs?|second[oi]|hours?|hrs?|or[ae]";

/** "3 minuti", "12–14 minutes", "ten minutes", "1 ora". Range keeps the low end. */
const TIME_RE = new RegExp(
  `(?<![\\p{L}\\d])(${Object.keys(NUMBER_WORDS).join("|")}|${NUMBER})` +
    `(?:\\s*(?:[–—-]|to)\\s*(${NUMBER}))?\\s*(${UNIT})(?![\\p{L}])`,
  "giu",
);

/** "Soffritto: Nella pentola…" — a short lead-in before a colon is the step's title. */
const TITLE_RE = /^([^:.!?\n]{2,42}):\s+([\s\S]+)$/;

/** Longer than this is not a cooking timer, it is a misread. */
const MAX_TIMER_SECONDS = 6 * 3600;

/** Words too generic to tie an ingredient line to a step. */
const STOP_WORDS = new Set([
  "olive", "fresh", "cooked", "whole", "extra", "virgin", "chopped", "cherry",
  "mixed", "grated", "dried", "large", "small", "about", "cotte", "cotto",
  "secco", "fatto", "casa", "mesi", "pezzi", "cottura", "crudo", "avanzate",
  "mezza", "porzione", "spezzate", "grattugiato", "caldo", "fresco", "circa",
  "grams", "grammi", "teaspoons", "tablespoons", "cucchiaio", "cucchiai",
  "cucchiaino", "milliliters", "millilitri",
]);

/**
 * Split a method step into its title, body and tappable durations.
 * @param {string} raw
 * @param {number} index
 * @returns {ParsedStep}
 */
export function parseStep(raw, index) {
  const clean = raw.replace(/\*\*/g, "").trim();
  const titled = TITLE_RE.exec(clean);
  const title = titled ? titled[1].trim() : null;
  const body = titled ? titled[2] : clean;

  /** @type {StepSegment[]} */
  const segments = [];
  /** @type {StepTime[]} */
  const times = [];
  let last = 0;
  for (const match of body.matchAll(TIME_RE)) {
    const time = toStepTime(match[1], match[2], match[3]);
    if (time === null || match.index === undefined) {
      continue;
    }
    if (match.index > last) {
      segments.push({ text: body.slice(last, match.index), time: null });
    }
    segments.push({ text: match[0], time });
    if (!times.some((t) => t.seconds === time.seconds)) {
      times.push(time);
    }
    last = match.index + match[0].length;
  }
  if (last < body.length) {
    segments.push({ text: body.slice(last), time: null });
  }
  return { title, body, segments, times, short: title ?? `Step ${index + 1}` };
}

/**
 * @param {string} low
 * @param {string | undefined} high
 * @param {string} unit
 * @returns {StepTime | null}
 */
function toStepTime(low, high, unit) {
  const lower = low.toLowerCase();
  const value = NUMBER_WORDS[lower] ?? parseFloat(lower.replace(",", "."));
  const u = unit.toLowerCase();
  const multiplier = u.startsWith("s") ? 1 : /^(h|or)/.test(u) ? 3600 : 60;
  const seconds = Math.round(value * multiplier);
  if (!Number.isFinite(seconds) || seconds <= 0 || seconds > MAX_TIMER_SECONDS) {
    return null;
  }
  if (high === undefined) {
    return { seconds, label: formatDuration(seconds) };
  }
  const short = multiplier === 1 ? "sec" : multiplier === 60 ? "min" : "h";
  return { seconds, label: `${low}–${high} ${short}` };
}

/**
 * "45 sec", "3 min", "1 h 30 min".
 * @param {number} seconds
 * @returns {string}
 */
export function formatDuration(seconds) {
  if (seconds < 60) {
    return `${seconds} sec`;
  }
  if (seconds < 3600) {
    return `${Math.round(seconds / 6) / 10} min`;
  }
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  return minutes ? `${hours} h ${minutes} min` : `${hours} h`;
}

/**
 * A countdown clock: "4:05", or "1:02:09" past the hour.
 * @param {number} seconds
 * @returns {string}
 */
export function formatClock(seconds) {
  const total = Math.max(0, Math.ceil(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/**
 * Whether an ingredient line is mentioned in a step's text. Matches on the
 * distinctive words of the line's name (before any comma or bracket).
 * @param {string} ingredient
 * @param {string} stepText
 * @returns {boolean}
 */
export function mentionsIngredient(ingredient, stepText) {
  const text = stepText.toLowerCase();
  return ingredient
    .split(/[,(]/)[0]
    .toLowerCase()
    .split(/[^\p{L}]+/u)
    .filter((word) => word.length >= 4 && !STOP_WORDS.has(word))
    .some((word) => text.includes(word));
}
