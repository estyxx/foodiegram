// @ts-check

import { CATEGORY } from "../lib/categories.js";

/**
 * A colour-coded Mediterranean-category chip: dot (or ring) plus text label.
 * Colour never carries meaning alone — the label always renders alongside it.
 * @param {string} categoryKey
 * @returns {HTMLElement}
 */
export function CategoryChip(categoryKey) {
  const tokens = CATEGORY[categoryKey];

  const chip = document.createElement("span");
  chip.className = "category-chip";
  chip.style.setProperty(
    "--chip-bg",
    tokens ? `var(${tokens.bg})` : "var(--surface-tint)",
  );
  chip.style.setProperty(
    "--chip-fg",
    tokens ? `var(${tokens.fg})` : "var(--ink-muted)",
  );
  chip.style.setProperty("--dot", tokens ? `var(${tokens.dot})` : "var(--ink-faint)");

  const dot = document.createElement("span");
  dot.className =
    tokens?.ring ? "category-chip__dot category-chip__dot--ring" : "category-chip__dot";

  const text = document.createElement("span");
  text.textContent = tokens ? tokens.label : categoryKey;

  chip.append(dot, text);
  return chip;
}
