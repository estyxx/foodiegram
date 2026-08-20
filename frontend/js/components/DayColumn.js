// @ts-check

import { GapSuggestions } from "./GapSuggestions.js";
import { displayTitle } from "../lib/format.js";
import { MEAL_SLOTS } from "../lib/week.js";

/** @typedef {import("../lib/week.js").MealSlot} MealSlot */
/** @typedef {import("../api/client.js").PlannedMeal} PlannedMeal */
/** @typedef {import("../api/client.js").CategoryStatus} CategoryStatus */
/** @typedef {import("../api/client.js").GapSuggestion} GapSuggestion */
/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */

/**
 * The display fields a placed-meal card needs, resolved from either a
 * gap-suggestion/search result (already a RecipeSummary) or a fetched
 * RecipeDetail — both carry these fields.
 * @typedef {object} MealDisplay
 * @property {string} code
 * @property {string | null} title
 * @property {string | null} author_username
 * @property {string | null} thumbnail_url
 * @property {string | null} cloudinary_url
 */

/**
 * @typedef {object} DayColumnHandlers
 * @property {(day: string, meal: MealSlot, recipe: RecipeSummary) => void} onAdd
 * @property {(plannedMeal: PlannedMeal, portions: number) => void} onPortionsChange
 * @property {(plannedMeal: PlannedMeal) => void} onRemove
 * @property {(query: string) => Promise<RecipeSummary[]>} onSearch
 */

/**
 * @typedef {object} DayColumnData
 * @property {string} day ISO date.
 * @property {string} label Display label, e.g. "lun 24 ago".
 * @property {boolean} isToday
 * @property {Partial<Record<MealSlot, PlannedMeal>>} meals
 * @property {(code: string) => MealDisplay | undefined} resolve
 * @property {CategoryStatus[]} balance
 * @property {GapSuggestion[]} suggestions
 */

/**
 * @typedef {object} DayColumnView
 * @property {HTMLElement} element
 * @property {(data: DayColumnData) => void} render
 */

/**
 * One day's lunch/dinner slots. Each empty slot's "+ add" opens the ranked
 * gap-suggestions picker inline — the keyboard-accessible alternative PLAN.md
 * calls for in place of pointer drag-and-drop.
 * @param {DayColumnHandlers} handlers
 * @returns {DayColumnView}
 */
export function DayColumn(handlers) {
  const column = document.createElement("div");
  column.className = "day-column";

  const heading = document.createElement("h3");
  heading.className = "day-column__heading";

  const slots = document.createElement("div");
  slots.className = "day-column__slots";

  column.append(heading, slots);

  const built = MEAL_SLOTS.map((meal) => buildSlot(meal, handlers));
  slots.append(...built.map((slot) => slot.element));

  return {
    element: column,
    render(data) {
      heading.textContent = data.label;
      column.classList.toggle("day-column--today", data.isToday);
      for (const slot of built) {
        const plannedMeal = data.meals[slot.meal];
        slot.render({
          day: data.day,
          plannedMeal: plannedMeal ?? null,
          display: plannedMeal ? data.resolve(plannedMeal.recipe_code) : undefined,
          balance: data.balance,
          suggestions: data.suggestions,
        });
      }
    },
  };
}

/**
 * @typedef {object} SlotData
 * @property {string} day
 * @property {PlannedMeal | null} plannedMeal
 * @property {MealDisplay | undefined} display
 * @property {CategoryStatus[]} balance
 * @property {GapSuggestion[]} suggestions
 */

/**
 * @typedef {object} Slot
 * @property {MealSlot} meal
 * @property {HTMLElement} element
 * @property {(data: SlotData) => void} render
 */

/**
 * @param {MealSlot} meal
 * @param {DayColumnHandlers} handlers
 * @returns {Slot}
 */
function buildSlot(meal, handlers) {
  const wrap = document.createElement("div");
  wrap.className = "day-slot";

  const label = document.createElement("span");
  label.className = "day-slot__label";
  label.textContent = meal === "lunch" ? "Lunch" : "Dinner";

  const body = document.createElement("div");
  body.className = "day-slot__body";

  wrap.append(label, body);

  let day = "";
  // Open/closed state for the picker lives here, independent of parent
  // re-renders — a full plan refresh from a sibling slot's action must not
  // slam this one's picker shut mid-interaction.
  let pickerOpen = false;

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "day-slot__add";
  addButton.textContent = "+ add";
  addButton.addEventListener("click", () => {
    pickerOpen = true;
    layout();
    picker.focusFirst();
  });

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn-ghost day-slot__cancel";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => {
    pickerOpen = false;
    layout();
    addButton.focus();
  });

  const picker = GapSuggestions({
    onSearch: handlers.onSearch,
    onAdd: (recipe) => {
      handlers.onAdd(day, meal, recipe);
      pickerOpen = false;
      layout();
    },
  });
  picker.element.classList.add("day-slot__picker");
  picker.element.append(cancel);

  /** @type {SlotData} */
  let latest = {
    day: "",
    plannedMeal: null,
    display: undefined,
    balance: [],
    suggestions: [],
  };

  function layout() {
    body.replaceChildren();
    if (latest.plannedMeal && latest.display) {
      body.append(
        buildMealCard(latest.plannedMeal, latest.display, handlers, () => {
          pickerOpen = true;
          layout();
          picker.focusFirst();
        }),
      );
      return;
    }
    if (pickerOpen) {
      body.append(picker.element);
    } else {
      body.append(addButton);
    }
  }

  return {
    meal,
    element: wrap,
    render(data) {
      day = data.day;
      latest = data;
      picker.render(data.balance, data.suggestions);
      layout();
    },
  };
}

/**
 * @param {PlannedMeal} plannedMeal
 * @param {MealDisplay} display
 * @param {DayColumnHandlers} handlers
 * @param {() => void} onChange
 * @returns {HTMLElement}
 */
function buildMealCard(plannedMeal, display, handlers, onChange) {
  const card = document.createElement("div");
  card.className = "meal-card";

  const src = display.cloudinary_url ?? display.thumbnail_url;
  if (src) {
    const img = document.createElement("img");
    img.className = "meal-card__img";
    img.src = src;
    img.alt = "";
    img.loading = "lazy";
    card.append(img);
  }

  const link = document.createElement("a");
  link.className = "meal-card__title";
  link.href = `#recipe/${display.code}`;
  link.textContent = displayTitle(display);
  card.append(link);

  const stepper = document.createElement("div");
  stepper.className = "meal-card__stepper";
  const dec = stepButton("−", "Fewer portions", () =>
    handlers.onPortionsChange(plannedMeal, Math.max(1, plannedMeal.portions - 1)),
  );
  const value = document.createElement("span");
  value.className = "meal-card__portions";
  value.textContent = String(plannedMeal.portions);
  const inc = stepButton("+", "More portions", () =>
    handlers.onPortionsChange(plannedMeal, plannedMeal.portions + 1),
  );
  stepper.append(dec, value, inc);
  card.append(stepper);

  const actions = document.createElement("div");
  actions.className = "meal-card__actions";
  const change = document.createElement("button");
  change.type = "button";
  change.className = "btn-ghost";
  change.textContent = "Change";
  change.addEventListener("click", onChange);
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "btn-ghost";
  remove.textContent = "Remove";
  remove.setAttribute("aria-label", `Remove ${displayTitle(display)}`);
  remove.addEventListener("click", () => handlers.onRemove(plannedMeal));
  actions.append(change, remove);
  card.append(actions);

  return card;
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
  button.className = "stepper__btn";
  button.textContent = glyph;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", onClick);
  return button;
}
