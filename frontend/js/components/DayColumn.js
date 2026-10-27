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
 *   Add a dish to the slot, beside any already there.
 * @property {(plannedMeal: PlannedMeal, recipe: RecipeSummary) => void} onReplace
 *   Swap one dish for another recipe ("Change").
 * @property {(plannedMeal: PlannedMeal, portions: number) => void} onPortionsChange
 * @property {(plannedMeal: PlannedMeal) => void} onRemove
 * @property {(query: string) => Promise<RecipeSummary[]>} onSearch
 * @property {(day: string, meal: MealSlot, base: RecipeSummary | null, replacing: PlannedMeal | null) => Promise<boolean>} onCustom
 *   Write "my version" for the slot (or in place of `replacing`); resolves
 *   true once saved and slotted.
 */

/**
 * @typedef {object} DayColumnData
 * @property {string} day ISO date.
 * @property {string} label Display label, e.g. "lun 24 ago".
 * @property {boolean} isToday
 * @property {Partial<Record<MealSlot, PlannedMeal[]>>} meals
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
 * One day's lunch/dinner slots. Each slot lists its dishes (a main and a side
 * can share one, D34); "+ add" opens the ranked gap-suggestions picker inline
 * — the keyboard-accessible alternative PLAN.md calls for in place of pointer
 * drag-and-drop.
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
        const dishes = [];
        for (const plannedMeal of data.meals[slot.meal] ?? []) {
          const display = data.resolve(plannedMeal.recipe_code);
          if (display) {
            dishes.push({ plannedMeal, display });
          }
        }
        slot.render({
          day: data.day,
          dishes,
          balance: data.balance,
          suggestions: data.suggestions,
        });
      }
    },
  };
}

/**
 * @typedef {object} Dish
 * @property {PlannedMeal} plannedMeal
 * @property {MealDisplay} display
 */

/**
 * @typedef {object} SlotData
 * @property {string} day
 * @property {Dish[]} dishes
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
  /**
   * The dish whose "Change" opened the picker; null when "+ add" did.
   * @type {PlannedMeal | null}
   */
  let replacing = null;

  const addButton = document.createElement("button");
  addButton.type = "button";
  addButton.className = "day-slot__add";
  addButton.textContent = "+ add";
  addButton.addEventListener("click", () => openPicker(null));

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn-ghost day-slot__cancel";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", () => {
    const opener = replacing;
    closePicker();
    // Back to whichever control opened the picker: that dish's "Change", or
    // "+ add".
    const change =
      opener?.id != null ? body.querySelector(`[data-change-id="${opener.id}"]`) : null;
    (change instanceof HTMLElement ? change : addButton).focus();
  });

  const picker = GapSuggestions({
    onSearch: handlers.onSearch,
    onAdd: (recipe) => {
      if (replacing) {
        handlers.onReplace(replacing, recipe);
      } else {
        handlers.onAdd(day, meal, recipe);
      }
      closePicker();
    },
    onCustom: async (base) => {
      // The picker stays open behind the dialog, so cancelling returns there.
      if (await handlers.onCustom(day, meal, base, replacing)) {
        closePicker();
      }
    },
  });
  picker.element.classList.add("day-slot__picker");
  picker.element.append(cancel);

  /** @type {SlotData} */
  let latest = {
    day: "",
    dishes: [],
    balance: [],
    suggestions: [],
  };

  /**
   * @param {PlannedMeal | null} target The dish to swap, or null to add one.
   */
  function openPicker(target) {
    replacing = target;
    pickerOpen = true;
    layout();
    picker.focusFirst();
  }

  function closePicker() {
    pickerOpen = false;
    replacing = null;
    layout();
  }

  function layout() {
    body.replaceChildren();
    // An open picker wins over the placed dishes: "Change" opens it on a slot
    // that already holds some.
    if (pickerOpen) {
      body.append(picker.element);
      return;
    }
    for (const dish of latest.dishes) {
      body.append(
        buildMealCard(dish.plannedMeal, dish.display, handlers, () =>
          openPicker(dish.plannedMeal),
        ),
      );
    }
    addButton.textContent = latest.dishes.length === 0 ? "+ add" : "+ add dish";
    body.append(addButton);
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
  change.className = "btn-ghost meal-card__change";
  change.textContent = "Change";
  change.setAttribute("aria-label", `Change ${displayTitle(display)}`);
  if (plannedMeal.id !== null) {
    change.dataset.changeId = String(plannedMeal.id);
  }
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
