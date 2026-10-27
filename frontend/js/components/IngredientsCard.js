// @ts-check

import { formatAmount } from "../lib/recipeDisplay.js";
import { formatQuantity } from "../lib/format.js";

/** @typedef {import("../lib/recipeDisplay.js").IngredientLayout} IngredientLayout */
/** @typedef {import("../lib/recipeDisplay.js").IngredientRow} IngredientRow */

/**
 * @typedef {object} IngredientsCardProps
 * @property {IngredientLayout} layout
 * @property {number | null} baseServings
 * @property {(ratio: number) => void} onRatioChange
 * @property {(message: string) => void} onAnnounce
 */

/**
 * The ingredients card: servings stepper, sections, and amounts you tap to
 * rescale everything. One shared ratio; the card re-renders on each change.
 * @param {IngredientsCardProps} props
 * @returns {HTMLElement}
 */
export function IngredientsCard({ layout, baseServings, onRatioChange, onAnnounce }) {
  const card = document.createElement("section");
  card.className = "ing-card";
  card.setAttribute("aria-label", "Ingredients");

  let ratio = 1;
  /** @type {number | null} row being edited, by ingredient index */
  let editing = null;

  const head = document.createElement("div");
  head.className = "ing-card__head";
  const title = document.createElement("h2");
  title.className = "ing-card__title";
  title.textContent = "Ingredients";
  head.append(title);

  const servings = document.createElement("span");
  servings.className = "ing-card__serves";
  if (baseServings !== null) {
    const group = document.createElement("div");
    group.className = "ing-card__stepper";
    group.setAttribute("role", "group");
    group.setAttribute("aria-label", "Servings");
    group.append(
      stepButton("−", "Fewer servings", () => stepServings(baseServings, -1)),
      servings,
      stepButton("+", "More servings", () => stepServings(baseServings, 1)),
    );
    head.append(group);
  }

  const hint = document.createElement("div");
  hint.className = "ing-card__hint";
  const hintText = document.createElement("span");
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "ing-card__reset";
  reset.textContent = "reset";
  reset.addEventListener("click", () => setRatio(1));
  hint.append(hintText, reset);

  const body = document.createElement("div");
  card.append(head, hint, body);
  render();
  return card;

  /**
   * @param {number} base
   * @param {number} delta
   */
  function stepServings(base, delta) {
    const current = Math.round(base * ratio);
    setRatio(Math.max(1, current + delta) / base);
  }

  /**
   * @param {number} next
   */
  function setRatio(next) {
    ratio = next;
    editing = null;
    onRatioChange(ratio);
    render();
  }

  function render() {
    const scaled = Math.abs(ratio - 1) >= 0.001;
    servings.replaceChildren(
      document.createTextNode(
        baseServings === null ? "" : `${formatQuantity(baseServings * ratio)} `,
      ),
      unitLabel("serv."),
    );
    const origin = baseServings === null ? "" : ` from ${baseServings}`;
    const lead = scaled
      ? `Rescaled${origin} ×${formatQuantity(ratio)}`
      : baseServings === null
        ? "Original amounts"
        : `Original · serves ${baseServings}`;
    hintText.textContent = `${lead} · tap an amount to rescale`;
    reset.hidden = !scaled;

    body.replaceChildren(
      ...layout.sections.map((section) => {
        const wrap = document.createElement("div");
        wrap.className = "ing-card__section";
        if (section.name) {
          const name = document.createElement("h3");
          name.className = "ing-card__section-name";
          name.textContent = section.name;
          wrap.append(name);
        }
        if (section.rows.length > 0) {
          const list = document.createElement("ul");
          list.className = "ing-card__list";
          list.append(...section.rows.map(buildRow));
          wrap.append(list);
        }
        if (section.toTaste.length > 0) {
          wrap.append(extraLine("To taste", section.toTaste.join(", ")));
        }
        return wrap;
      }),
    );
    if (layout.equipment.length > 0) {
      body.append(extraLine("Equipment", layout.equipment.join(", ")));
    }
  }

  /**
   * @param {IngredientRow} row
   * @returns {HTMLLIElement}
   */
  function buildRow(row) {
    const item = document.createElement("li");
    item.className = "ing-card__row";
    const amountCell = document.createElement("span");
    amountCell.className = "ing-card__amount";
    const name = document.createElement("span");
    name.className = "ing-card__name";
    name.textContent = row.name;
    item.append(amountCell, name);

    const quantity = row.quantity;
    if (quantity === null) {
      return item;
    }
    const amount = formatAmount(quantity, ratio);
    const label = `Amount of ${row.name}: ${[amount, row.unit].filter(Boolean).join(" ")}. Edit to rescale`;

    if (editing !== row.index) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "ing-card__qty";
      button.textContent = [amount, row.unit].filter(Boolean).join(" ");
      button.setAttribute("aria-label", label);
      button.addEventListener("click", () => {
        editing = row.index;
        render();
      });
      amountCell.append(button);
      return item;
    }

    const input = document.createElement("input");
    input.type = "text";
    input.inputMode = "decimal";
    input.className = "ing-card__input";
    input.value = formatQuantity(quantity.value * ratio);
    input.setAttribute("aria-label", label);
    let cancelled = false;
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        input.blur();
      } else if (event.key === "Escape") {
        // Esc only cancels the edit; it must not close anything around the card.
        event.stopPropagation();
        cancelled = true;
        input.blur();
      }
    });
    input.addEventListener("blur", () => {
      const typed = parseFloat(input.value.replace(",", "."));
      if (!cancelled && Number.isFinite(typed) && typed > 0) {
        const next = typed / quantity.value;
        setRatio(next);
        onAnnounce(`Rescaled everything ×${formatQuantity(next)}`);
      } else {
        editing = null;
        render();
      }
    });
    amountCell.append(input);
    if (row.unit) {
      amountCell.append(unitLabel(row.unit));
    }
    queueMicrotask(() => input.focus());
    return item;
  }
}

/**
 * @param {string} glyph
 * @param {string} label
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function stepButton(glyph, label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ing-card__step";
  button.textContent = glyph;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", onClick);
  return button;
}

/**
 * @param {string} text
 * @returns {HTMLSpanElement}
 */
function unitLabel(text) {
  const span = document.createElement("span");
  span.className = "ing-card__unit";
  span.textContent = text;
  return span;
}

/**
 * "TO TASTE · sale, pepe" and "EQUIPMENT · Stampo da 24 cm".
 * @param {string} label
 * @param {string} text
 * @returns {HTMLParagraphElement}
 */
function extraLine(label, text) {
  const line = document.createElement("p");
  line.className = "ing-card__extra";
  const tag = document.createElement("span");
  tag.className = "ing-card__extra-label";
  tag.textContent = `${label} · `;
  line.append(tag, document.createTextNode(text));
  return line;
}
