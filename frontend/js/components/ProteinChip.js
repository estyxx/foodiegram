// @ts-check

import { CATEGORY } from "../lib/categories.js";
import { formatPortion, portionWords } from "../lib/format.js";

/** @typedef {import("../api/client.js").CategoryServing} CategoryServing */

/**
 * A protein chip for the plan: category colour, dot (or ring), and the
 * portion it counts for when that is not a whole one ("½ Legumes").
 * @param {CategoryServing} serving
 * @returns {HTMLElement}
 */
export function ProteinChip(serving) {
  const tokens = CATEGORY[serving.category];
  const label = tokens ? tokens.label : serving.category;

  const chip = document.createElement("span");
  chip.className = "protein-chip";
  chip.style.setProperty("--chip-bg", tokens ? `var(${tokens.bg})` : "var(--surface-tint)");
  chip.style.setProperty("--chip-fg", tokens ? `var(${tokens.fg})` : "var(--ink-muted)");
  chip.style.setProperty("--dot", tokens ? `var(${tokens.dot})` : "var(--ink-faint)");

  const dot = document.createElement("span");
  dot.className = tokens?.ring ? "protein-chip__dot protein-chip__dot--ring" : "protein-chip__dot";
  dot.setAttribute("aria-hidden", "true");
  chip.append(dot);

  const portion = formatPortion(serving.servings);
  if (portion) {
    // The mono face cannot draw ½ legibly at chip size; Manrope can.
    const fraction = document.createElement("span");
    fraction.className = "protein-chip__portion";
    fraction.setAttribute("aria-hidden", "true");
    fraction.textContent = portion;
    chip.append(fraction);
  }

  const text = document.createElement("span");
  text.setAttribute("aria-hidden", "true");
  text.textContent = label;

  // aria-label on a plain span is not reliably read, so the spoken form
  // ("half portion Legumes") rides in hidden text instead.
  const spoken = document.createElement("span");
  spoken.className = "visually-hidden";
  const words = portionWords(serving.servings);
  spoken.textContent = words ? `${words} ${label}` : label;

  chip.append(text, spoken);
  return chip;
}

/**
 * The chips row for a recipe, or null when it tracks no protein (the row is
 * left out entirely rather than shown empty).
 * @param {CategoryServing[]} servings
 * @returns {HTMLElement | null}
 */
export function ProteinChips(servings) {
  const tracked = servings.filter((serving) => serving.servings > 0);
  if (tracked.length === 0) {
    return null;
  }
  const row = document.createElement("div");
  row.className = "protein-chips";
  row.append(...tracked.map(ProteinChip));
  return row;
}
