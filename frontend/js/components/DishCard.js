// @ts-check

import { ProteinChips } from "./ProteinChip.js";
import { displayTitle } from "../lib/format.js";

/** @typedef {import("../api/client.js").PlannedMeal} PlannedMeal */
/** @typedef {import("../api/client.js").CategoryServing} CategoryServing */

/**
 * The display fields a planned dish needs, resolved from the session index, a
 * picked search result, or a fetched RecipeDetail.
 * @typedef {object} MealDisplay
 * @property {string} code
 * @property {string | null} title
 * @property {string | null} author_username
 * @property {string | null} thumbnail_url
 * @property {string | null} cloudinary_url
 * @property {CategoryServing[]} category_servings
 */

/**
 * @typedef {object} Dish
 * @property {PlannedMeal} plannedMeal
 * @property {MealDisplay} display
 * @property {string} key "day-meal-index": stable across re-renders.
 */

/**
 * @typedef {object} DishHandlers
 * @property {(plannedMeal: PlannedMeal, portions: number) => void} onPortions
 * @property {(dish: Dish) => void} onChange Open the picker to swap this dish.
 * @property {(dish: Dish) => void} onRemove
 * @property {(key: string) => void} onToggleMenu Desktop ⋯ menu.
 */

/**
 * Desktop dish card: photo when the recipe has one, title, protein chips, a
 * compact servings stepper, and Change/Remove tucked behind ⋯.
 * @param {Dish} dish
 * @param {boolean} menuOpen
 * @param {DishHandlers} handlers
 * @returns {HTMLElement}
 */
export function DishCard(dish, menuOpen, handlers) {
  const card = document.createElement("div");
  card.className = "dish-card";

  const src = dish.display.cloudinary_url ?? dish.display.thumbnail_url;
  if (src) {
    const img = document.createElement("img");
    img.className = "dish-card__img";
    img.src = src;
    img.alt = "";
    img.loading = "lazy";
    // An expired Instagram URL shows nothing, not a broken-image box.
    img.addEventListener("error", () => img.remove());
    card.append(img);
  }

  card.append(titleLink(dish, "dish-card__title"));
  const chips = ProteinChips(dish.display.category_servings);
  if (chips) {
    card.append(chips);
  }

  const controls = document.createElement("div");
  controls.className = "dish-card__controls";
  controls.append(...stepper(dish, handlers, "dish-card"), igTag(dish, "dish-card__ig"));

  const title = displayTitle(dish.display);
  const more = document.createElement("button");
  more.type = "button";
  more.className = "dish-card__more";
  more.textContent = "⋯";
  more.dataset.focusKey = `menu-${dish.key}`;
  more.setAttribute("aria-label", `Options for ${title}`);
  more.setAttribute("aria-expanded", String(menuOpen));
  more.addEventListener("click", () => handlers.onToggleMenu(dish.key));
  controls.append(more);
  card.append(controls);

  if (menuOpen) {
    const actions = document.createElement("div");
    actions.className = "dish-card__actions";
    const change = actionButton("Change", `Change ${title}`, "dish-card__action", () =>
      handlers.onChange(dish),
    );
    change.dataset.focusKey = `change-${dish.key}`;
    const remove = actionButton(
      "Remove",
      `Remove ${title}`,
      "dish-card__action dish-card__action--remove",
      () => handlers.onRemove(dish),
    );
    remove.dataset.focusKey = `remove-${dish.key}`;
    actions.append(change, remove);
    card.append(actions);
  }
  return card;
}

/**
 * Mobile dish card: the same dish with every control out in the open at
 * thumb size (40px targets) — no ⋯ menu, no photo.
 * @param {Dish} dish
 * @param {DishHandlers} handlers
 * @returns {HTMLElement}
 */
export function MobileDishCard(dish, handlers) {
  const card = document.createElement("div");
  card.className = "dish-card dish-card--mobile";

  card.append(titleLink(dish, "dish-card__title"));
  const chips = ProteinChips(dish.display.category_servings);
  if (chips) {
    card.append(chips);
  }

  const title = displayTitle(dish.display);
  const controls = document.createElement("div");
  controls.className = "dish-card__controls";
  const change = actionButton("Change", `Change ${title}`, "dish-card__change", () =>
    handlers.onChange(dish),
  );
  change.dataset.focusKey = `change-${dish.key}`;
  const remove = actionButton("×", `Remove ${title}`, "dish-card__remove", () =>
    handlers.onRemove(dish),
  );
  remove.dataset.focusKey = `remove-${dish.key}`;
  controls.append(...stepper(dish, handlers, "dish-card"), igTag(dish, "dish-card__ig"), change, remove);
  card.append(controls);
  return card;
}

/**
 * @param {Dish} dish
 * @param {string} className
 * @returns {HTMLAnchorElement}
 */
function titleLink(dish, className) {
  const link = document.createElement("a");
  link.className = className;
  link.href = `#recipe/${dish.display.code}`;
  link.textContent = displayTitle(dish.display);
  return link;
}

/**
 * −, the servings count, + — never below one.
 * @param {Dish} dish
 * @param {DishHandlers} handlers
 * @param {string} block
 * @returns {HTMLElement[]}
 */
function stepper(dish, handlers, block) {
  const { plannedMeal } = dish;
  const title = displayTitle(dish.display);
  const dec = actionButton(
    "−",
    `Fewer servings of ${title}, now ${plannedMeal.portions}`,
    `${block}__step`,
    () => handlers.onPortions(plannedMeal, Math.max(1, plannedMeal.portions - 1)),
  );
  dec.dataset.focusKey = `dec-${dish.key}`;
  const value = document.createElement("span");
  value.className = `${block}__servings`;
  value.textContent = String(plannedMeal.portions);
  const inc = actionButton(
    "+",
    `More servings of ${title}, now ${plannedMeal.portions}`,
    `${block}__step`,
    () => handlers.onPortions(plannedMeal, plannedMeal.portions + 1),
  );
  inc.dataset.focusKey = `inc-${dish.key}`;
  return [dec, value, inc];
}

/**
 * "IG" for a save from Instagram; an empty span keeps the row's spacing.
 * @param {Dish} dish
 * @param {string} className
 * @returns {HTMLElement}
 */
function igTag(dish, className) {
  const tag = document.createElement("span");
  tag.className = className;
  if (dish.display.author_username !== null) {
    tag.textContent = "IG";
    tag.title = `From Instagram, @${dish.display.author_username}`;
  }
  return tag;
}

/**
 * @param {string} text
 * @param {string} label
 * @param {string} className
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function actionButton(text, label, className, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.textContent = text;
  if (label !== text) {
    button.setAttribute("aria-label", label);
  }
  button.addEventListener("click", onClick);
  return button;
}
