// @ts-check

import { humanise } from "../lib/format.js";

/**
 * A small labelled chip. Text is set via textContent (never innerHTML).
 * @param {string} label
 * @param {{ variant?: "default" | "plant" }} [options]
 * @returns {HTMLSpanElement}
 */
export function Chip(label, options) {
  const el = document.createElement("span");
  el.className = "chip";
  if (options?.variant === "plant") {
    el.classList.add("badge-plant");
  }
  el.textContent = humanise(label);
  return el;
}
