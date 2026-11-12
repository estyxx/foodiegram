// @ts-check

import { CATEGORY } from "./categories.js";

/** @typedef {import("../api/client.js").MedCategory} MedCategory */

export const SERVINGS_STEP = "0.25";
export const DEFAULT_SERVINGS = "1";

/**
 * Split a textarea value into trimmed, non-empty lines.
 * @param {string} text
 * @returns {string[]}
 */
export function lines(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "");
}

/**
 * A labelled single-line or multi-line text control.
 * @template {"input" | "textarea"} K
 * @param {string} label
 * @param {K} tag
 * @param {string} value
 * @returns {{ element: HTMLLabelElement, control: HTMLElementTagNameMap[K] }}
 */
export function textField(label, tag, value) {
  const wrap = document.createElement("label");
  wrap.className = "custom-recipe__field";
  const text = document.createElement("span");
  text.className = "custom-recipe__label";
  text.textContent = label;
  const control = document.createElement(tag);
  control.className = "custom-recipe__control";
  control.value = value;
  if (control instanceof HTMLTextAreaElement) {
    control.rows = 5;
  }
  wrap.append(text, control);
  return { element: wrap, control };
}

/**
 * One checkbox + servings per Mediterranean category, prefilled from a recipe.
 * These are what the weekly balance counts, so the user sets them by hand;
 * nothing is inferred.
 * @param {MedCategory[]} current
 * @returns {{ element: HTMLFieldSetElement, read: () => MedCategory[] }}
 */
export function categoryFieldset(current) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "custom-recipe__categories";
  const legend = document.createElement("legend");
  legend.className = "custom-recipe__label";
  legend.textContent = "Counts toward (servings per portion)";
  fieldset.append(legend);

  const byCategory = new Map(current.map((serving) => [serving.category, serving]));
  /** @type {(() => MedCategory | null)[]} */
  const readers = [];

  for (const [key, tokens] of Object.entries(CATEGORY)) {
    const existing = byCategory.get(key);
    const row = document.createElement("div");
    row.className = "custom-recipe__category";

    const checkLabel = document.createElement("label");
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = existing !== undefined;
    checkLabel.append(check, document.createTextNode(` ${tokens.label}`));

    const servings = document.createElement("input");
    servings.type = "number";
    servings.className = "custom-recipe__servings";
    servings.min = SERVINGS_STEP;
    servings.step = SERVINGS_STEP;
    servings.value = existing ? String(existing.servings) : DEFAULT_SERVINGS;
    servings.disabled = !check.checked;
    servings.setAttribute("aria-label", `${tokens.label} servings`);
    check.addEventListener("change", () => {
      servings.disabled = !check.checked;
    });
    row.append(checkLabel, servings);

    /** @type {HTMLInputElement | null} */
    let oily = null;
    if (key === "fish") {
      const oilyLabel = document.createElement("label");
      const oilyCheck = document.createElement("input");
      oilyCheck.type = "checkbox";
      oilyCheck.checked = existing?.is_oily_fish ?? false;
      oilyLabel.append(oilyCheck, document.createTextNode(" oily"));
      row.append(oilyLabel);
      oily = oilyCheck;
    }

    fieldset.append(row);
    readers.push(() => {
      const amount = Number(servings.value);
      if (!check.checked || !(amount > 0)) {
        return null;
      }
      return { category: key, servings: amount, is_oily_fish: oily?.checked ?? false };
    });
  }

  return {
    element: fieldset,
    read: () => readers.map((reader) => reader()).filter((serving) => serving !== null),
  };
}
