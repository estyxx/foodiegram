// @ts-check

/** Match the first number (int or decimal) in a string. Mirrors the /scale API. */
const NUMBER_RE = /(\d+\.?\d*)/;

/**
 * Extract the first numeric value from an ingredient line.
 * @param {string} text
 * @returns {number | null}
 */
export function extractNumber(text) {
  const match = text.match(NUMBER_RE);
  return match ? parseFloat(match[1]) : null;
}

/**
 * Scale every number in an ingredient line by factor, rounded to 2 dp.
 * @param {string} raw
 * @param {number} factor
 * @returns {string}
 */
export function scaleIngredient(raw, factor) {
  return raw.replace(/(\d+\.?\d*)/g, (match) => {
    const scaled = Math.round(parseFloat(match) * factor * 100) / 100;
    return String(scaled);
  });
}
