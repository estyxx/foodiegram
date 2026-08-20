// @ts-check

import { CategoryChip } from "./CategoryChip.js";
import { CATEGORY } from "../lib/categories.js";
import { formatServings } from "../lib/format.js";

/** @typedef {import("../api/client.js").CategoryStatus} CategoryStatus */

const STATE_LABEL = /** @type {Record<CategoryStatus["state"], string>} */ ({
  under: "Room left",
  ok: "On track",
  over: "Over target",
});

/**
 * @typedef {object} BalancePanelView
 * @property {HTMLElement} element
 * @property {(balance: CategoryStatus[], oilyFish: number) => void} render
 */

/**
 * THE component: one bar per Mediterranean category, graded under/on-track/
 * over against its weekly target range. Balance changes are announced via a
 * live region so the "watch it move" payoff isn't visual-only.
 * @returns {BalancePanelView}
 */
export function BalancePanel() {
  const section = document.createElement("section");
  section.className = "balance-panel";
  section.setAttribute("aria-label", "Weekly Mediterranean balance");

  const title = document.createElement("h2");
  title.className = "balance-panel__title";
  title.textContent = "This week's balance";

  const rows = document.createElement("div");
  rows.className = "balance-panel__rows";

  const oily = document.createElement("p");
  oily.className = "balance-panel__oily";

  const announce = document.createElement("p");
  announce.className = "visually-hidden";
  announce.setAttribute("aria-live", "polite");

  section.append(title, rows, oily, announce);

  return {
    element: section,
    render(balance, oilyFish) {
      rows.replaceChildren(...balance.map(buildRow));
      oily.textContent = `Oily fish: ${formatServings(oilyFish)} this week (aim ≥ 1)`;
      announce.textContent = balance
        .map((status) => {
          const label = CATEGORY[status.category]?.label ?? status.category;
          return `${label}: ${STATE_LABEL[status.state]}`;
        })
        .join(". ");
    },
  };
}

/**
 * @param {CategoryStatus} status
 * @returns {HTMLElement}
 */
function buildRow(status) {
  const row = document.createElement("div");
  row.className = "balance-row";

  const chip = CategoryChip(status.category);
  chip.classList.add("balance-row__chip");

  const track = document.createElement("div");
  track.className = "balance-row__track";
  // Each row scales to its own range so a small target (poultry: 1-2) and a
  // large one (dairy: 0-7) both stay legible; the numbers alongside are what
  // make the bars comparable, not their shared length.
  const scale = Math.max(status.planned, status.max_servings, 1) * 1.15;

  const range = document.createElement("div");
  range.className = "balance-row__range";
  range.style.left = `${(status.min_servings / scale) * 100}%`;
  range.style.width = `${((status.max_servings - status.min_servings) / scale) * 100}%`;

  const fill = document.createElement("div");
  fill.className = `balance-row__fill balance-row__fill--${status.state}`;
  fill.style.width = `${Math.min(status.planned / scale, 1) * 100}%`;

  track.append(range, fill);

  const numbers = document.createElement("span");
  numbers.className = "balance-row__numbers";
  numbers.textContent =
    `${formatServings(status.planned)} / ${formatServings(status.min_servings)}` +
    `–${formatServings(status.max_servings)}`;

  const state = document.createElement("span");
  state.className = `balance-row__state balance-row__state--${status.state}`;
  state.textContent = STATE_LABEL[status.state];

  row.append(chip, track, numbers, state);
  return row;
}
