// @ts-check

import { capitalise, formatQuantity } from "./format.js";

/**
 * A leading amount, e.g. "2–3" in "2–3 uova". `high` is set for a range.
 * @typedef {object} Quantity
 * @property {number} value
 * @property {number | null} high
 */
/**
 * One ingredient as the page shows it. `quantity` is null for a line whose
 * number is not a leading amount ("riso 160 g", "farina 00"): it is shown
 * verbatim and never scaled.
 * @typedef {object} IngredientRow
 * @property {number} index position in recipe.ingredients
 * @property {Quantity | null} quantity
 * @property {string} unit
 * @property {string} name
 */
/**
 * @typedef {object} IngredientSection
 * @property {string} name "" for the lines before the first label
 * @property {IngredientRow[]} rows
 * @property {string[]} toTaste lines with no amount at all
 */
/**
 * @typedef {object} IngredientLayout
 * @property {IngredientSection[]} sections
 * @property {string[]} equipment
 * @property {number} count every ingredient line, equipment aside
 */
/**
 * @typedef {object} TitleParts
 * @property {string} lead plain part of the heading
 * @property {string} emphasis italicised tail ("" when a subtitle is used)
 * @property {string} subtitle from a "(…)" in the title
 */

/** "FROLLA: 210 g farina" starts a section named Frolla. */
const SECTION_RE = /^([A-ZÀ-Ù][A-ZÀ-Ù ]{2,}):\s*(.+)$/;

const FRACTIONS = /** @type {Record<string, number>} */ ({ "½": 0.5, "¼": 0.25, "¾": 0.75 });

const NUMBER = "\\d+(?:[.,]\\d+)?(?:\\s*\\/\\s*\\d+)?|[½¼¾]";

/**
 * Units worth keeping beside the amount (Italian and English, as captions
 * write them). Anything else stays part of the name: "2 carote".
 */
const UNITS = [
  "kg", "g", "gr", "grammi", "mg", "ml", "cl", "dl", "l", "litri?", "cm", "mm",
  "oz", "lb", "lbs", "tbsp", "tsp", "cups?", "cucchia(?:io|i)", "cucchiain[oi]",
  "pizzic(?:o|hi)", "spicchi?o?", "bicchier[ei]", "tazz[ae]", "fett[ae]",
  "rotol[oi]", "mazzett?[oi]", "manciat[ae]", "handfuls?", "pinch(?:es)?",
  "cloves?", "cans?", "bunch(?:es)?", "slices?",
].join("|");

/** "160g riso", "2–3 uova", "1/2 cipolla", "1 cucchiaio di olio". */
const LEADING_RE = new RegExp(
  `^(${NUMBER})(?:\\s*[–—-]\\s*(${NUMBER}))?\\s*(?:(${UNITS})\\.?(?![\\p{L}]))?\\s*(.*)$`,
  "iu",
);

const HAS_DIGIT_RE = /\d/;

/**
 * Group a recipe's raw ingredient lines for display. Stored lines are never
 * changed; this only decides how each one is shown.
 * @param {readonly string[]} lines
 * @returns {IngredientLayout}
 */
export function layoutIngredients(lines) {
  /** @type {IngredientSection} */
  let current = { name: "", rows: [], toTaste: [] };
  const sections = [current];
  /** @type {string[]} */
  const equipment = [];

  lines.forEach((raw, index) => {
    let line = raw.trim();
    const labelled = SECTION_RE.exec(line);
    if (labelled) {
      current = { name: capitalise(labelled[1].trim().toLowerCase()), rows: [], toTaste: [] };
      sections.push(current);
      line = labelled[2].trim();
    }

    const row = parseLine(line, index);
    if (/^stampo/i.test(line) || row.unit.toLowerCase() === "cm") {
      equipment.push(line);
    } else if (row.quantity === null && !HAS_DIGIT_RE.test(line)) {
      current.toTaste.push(line);
    } else {
      current.rows.push(row);
    }
  });

  const kept = sections.filter((s) => s.rows.length > 0 || s.toTaste.length > 0);
  const count = kept.reduce((n, s) => n + s.rows.length + s.toTaste.length, 0);
  return { sections: kept, equipment, count };
}

/**
 * @param {string} line
 * @param {number} index
 * @returns {IngredientRow}
 */
function parseLine(line, index) {
  const match = LEADING_RE.exec(line);
  const value = match ? toNumber(match[1]) : null;
  if (match === null || value === null || value <= 0 || match[4] === "") {
    return { index, quantity: null, unit: "", name: line };
  }
  return {
    index,
    quantity: { value, high: match[2] ? toNumber(match[2]) : null },
    unit: match[3] ?? "",
    name: match[4],
  };
}

/**
 * @param {string} text "160", "0,5", "1/2" or "½"
 * @returns {number | null}
 */
function toNumber(text) {
  if (text in FRACTIONS) {
    return FRACTIONS[text];
  }
  const [top, bottom] = text.replace(",", ".").split("/").map((part) => parseFloat(part));
  if (bottom === undefined) {
    return Number.isFinite(top) ? top : null;
  }
  return Number.isFinite(top) && Number.isFinite(bottom) && bottom > 0 ? top / bottom : null;
}

/**
 * The amount as shown, scaled: "160", "0.5", "2–3".
 * @param {Quantity} quantity
 * @param {number} ratio
 * @returns {string}
 */
export function formatAmount(quantity, ratio) {
  const low = formatQuantity(quantity.value * ratio);
  return quantity.high === null ? low : `${low}–${formatQuantity(quantity.high * ratio)}`;
}

/**
 * One ingredient as a plain-text line, scaled (for copy and export).
 * @param {IngredientRow} row
 * @param {number} ratio
 * @returns {string}
 */
export function rowText(row, ratio) {
  if (row.quantity === null) {
    return row.name;
  }
  const amount = [formatAmount(row.quantity, ratio), row.unit].filter(Boolean).join(" ");
  return `${amount} ${row.name}`;
}

/**
 * Split a title into its heading, italic tail and subtitle. A "(…)" becomes
 * the subtitle; otherwise the last word (or the "all'…" phrase) is the tail.
 * @param {string} title
 * @returns {TitleParts}
 */
export function splitTitle(title) {
  const open = title.indexOf("(");
  if (open > 0) {
    const subtitle = title.slice(open + 1).replace(/\)\s*$/, "").trim();
    return { lead: title.slice(0, open).trim(), emphasis: "", subtitle: capitalise(subtitle) };
  }
  const all = title.indexOf("all'");
  if (all > 0) {
    return { lead: title.slice(0, all), emphasis: title.slice(all), subtitle: "" };
  }
  const words = title.split(" ");
  if (words.length < 2) {
    return { lead: "", emphasis: title, subtitle: "" };
  }
  return {
    lead: `${words.slice(0, -1).join(" ")} `,
    emphasis: words[words.length - 1],
    subtitle: "",
  };
}
