// @ts-check

import { CATEGORY, CATEGORY_ORDER } from "../lib/categories.js";
import { formatQuantity } from "../lib/format.js";

/** @typedef {import("../api/client.js").CategoryStatus} CategoryStatus */

/** @type {Record<CategoryStatus["state"], string>} */
const STATE_LABEL = { under: "Room left", ok: "On track", over: "Over" };

/** @type {Record<CategoryStatus["state"], string>} */
const STATE_SPOKEN = { under: "Room left", ok: "On track", over: "Over target" };

/**
 * The server's balance in display order (cool colours first). The FE does no
 * balance math: totals and states come from the plan payload as-is.
 * @param {CategoryStatus[]} balance
 * @returns {CategoryStatus[]}
 */
export function orderedBalance(balance) {
  const rank = (/** @type {string} */ key) => {
    const at = CATEGORY_ORDER.indexOf(key);
    return at === -1 ? CATEGORY_ORDER.length : at;
  };
  return [...balance].sort((a, b) => rank(a.category) - rank(b.category));
}

/**
 * @typedef {object} BalanceStripView
 * @property {HTMLElement} element
 * @property {(balance: CategoryStatus[]) => void} render
 */

/**
 * Desktop: the week's balance as one pinned strip of eight tiles, so it stays
 * in view while dishes are added below it.
 * @returns {BalanceStripView}
 */
export function BalanceStrip() {
  const pin = document.createElement("div");
  pin.className = "balance-strip";

  const card = document.createElement("div");
  card.className = "balance-strip__card";
  card.setAttribute("role", "region");
  card.setAttribute("aria-label", "This week's balance");
  pin.append(card);

  return {
    element: pin,
    render(balance) {
      card.replaceChildren(...orderedBalance(balance).map((status) => buildTile(status, "strip")));
    },
  };
}

/**
 * @typedef {object} BalanceBarView
 * @property {HTMLElement} element
 * @property {(balance: CategoryStatus[], open: boolean) => void} render
 */

/**
 * Mobile: the balance folded into one bar (a dot per category and a one-line
 * summary) that opens to the same tiles.
 * @param {() => void} onToggle
 * @returns {BalanceBarView}
 */
export function BalanceBar(onToggle) {
  const card = document.createElement("div");
  card.className = "balance-bar";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "balance-bar__toggle";
  toggle.dataset.focusKey = "balance-toggle";
  toggle.addEventListener("click", onToggle);

  const title = document.createElement("span");
  title.className = "balance-bar__title";
  title.textContent = "Balance";

  const dots = document.createElement("span");
  dots.className = "balance-bar__dots";
  dots.setAttribute("aria-hidden", "true");

  const summary = document.createElement("span");
  summary.className = "balance-bar__summary";

  const chevron = document.createElement("span");
  chevron.className = "balance-bar__chevron";
  chevron.setAttribute("aria-hidden", "true");
  chevron.textContent = "▾";

  toggle.append(title, dots, summary, chevron);

  const tiles = document.createElement("div");
  tiles.className = "balance-bar__tiles";
  tiles.id = "balance-bar-tiles";
  toggle.setAttribute("aria-controls", tiles.id);

  card.append(toggle, tiles);

  return {
    element: card,
    render(balance, open) {
      const ordered = orderedBalance(balance);
      dots.replaceChildren(
        ...ordered.map((status) => {
          const dot = document.createElement("span");
          dot.className = `balance-bar__dot balance-fill--${status.state}`;
          return dot;
        }),
      );
      const over = ordered.filter((status) => status.state === "over").length;
      const room = ordered.filter((status) => status.state === "under").length;
      const parts = [over ? `${over} over` : "", room ? `${room} room left` : ""].filter(Boolean);
      summary.textContent = parts.join(" · ") || "all on track";
      summary.classList.toggle("balance-bar__summary--over", over > 0);
      toggle.setAttribute("aria-expanded", String(open));
      card.classList.toggle("balance-bar--open", open);
      tiles.hidden = !open;
      tiles.replaceChildren(...ordered.map((status) => buildTile(status, "bar")));
    },
  };
}

/**
 * One category tile: label, value against target, meter, and status.
 * @param {CategoryStatus} status
 * @param {"strip" | "bar"} variant
 * @returns {HTMLElement}
 */
function buildTile(status, variant) {
  const tokens = CATEGORY[status.category];
  const label = tokens ? tokens.label : status.category;
  const target =
    status.min_servings === status.max_servings
      ? formatQuantity(status.max_servings)
      : `${formatQuantity(status.min_servings)}–${formatQuantity(status.max_servings)}`;
  const value = formatQuantity(status.planned);

  const tile = document.createElement("div");
  tile.className = `balance-tile balance-tile--${variant}`;
  tile.setAttribute("role", "group");
  tile.setAttribute("aria-label", `${label}: ${value} of ${target}. ${STATE_SPOKEN[status.state]}`);
  if (tokens) {
    tile.style.setProperty("--tile-fg", `var(${tokens.fg})`);
    tile.style.setProperty("--dot", `var(${tokens.dot})`);
  }

  const name = document.createElement("span");
  name.className = "balance-tile__label";
  const dot = document.createElement("span");
  dot.className = tokens?.ring ? "balance-tile__dot balance-tile__dot--ring" : "balance-tile__dot";
  dot.setAttribute("aria-hidden", "true");
  name.append(dot, variant === "strip" && tokens ? tokens.short : label);

  const numbers = document.createElement("span");
  numbers.className = "balance-tile__numbers";
  const big = document.createElement("span");
  big.className = "balance-tile__value";
  big.textContent = value;
  const of = document.createElement("span");
  of.className = "balance-tile__target";
  of.textContent = `/ ${target}`;
  numbers.append(big, of);

  const state = document.createElement("span");
  state.className = `balance-tile__state balance-state--${status.state}`;
  state.textContent = STATE_LABEL[status.state];

  // The scale leaves headroom past the target band so "over" reads as over.
  const scale = Math.max(status.max_servings * 1.35, status.planned * 1.08, 1.5);
  const meter = document.createElement("span");
  meter.className = "balance-tile__meter";
  meter.setAttribute("aria-hidden", "true");
  const band = document.createElement("span");
  band.className = "balance-tile__band";
  band.style.left = `${(status.min_servings / scale) * 100}%`;
  band.style.width = `${((status.max_servings - status.min_servings) / scale) * 100}%`;
  const fill = document.createElement("span");
  fill.className = `balance-tile__fill balance-fill--${status.state}`;
  fill.style.width = `${Math.min(100, (status.planned / scale) * 100)}%`;
  meter.append(band, fill);

  if (variant === "bar") {
    // Mobile keeps the status on the value row to save a line.
    numbers.append(state);
    tile.append(name, numbers, meter);
  } else {
    tile.append(name, numbers, meter, state);
  }
  return tile;
}
