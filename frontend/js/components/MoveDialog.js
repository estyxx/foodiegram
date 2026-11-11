// @ts-check

import { SLOT_LABEL } from "./WeekBoard.js";
import { displayTitle } from "../lib/format.js";
import { MEAL_SLOTS } from "../lib/week.js";

/** @typedef {import("../lib/week.js").MealSlot} MealSlot */
/** @typedef {import("./DishCard.js").Dish} Dish */
/** @typedef {import("./WeekBoard.js").PlanDay} PlanDay */

/**
 * @typedef {object} MoveRequest
 * @property {Dish} dish
 * @property {PlanDay[]} days Every day of the week, weekend included.
 * @property {(day: PlanDay, meal: MealSlot) => void} onMove
 * @property {() => void} onClose Fires when it closes without a move.
 */

/**
 * @typedef {object} MoveDialogView
 * @property {HTMLDialogElement} element
 * @property {(request: MoveRequest) => void} open
 */

/**
 * "Move to…": every lunch and dinner of the week as a button. The menu path
 * for what drag and drop does on the desktop board (PLAN §15.6), and the only
 * way to move a dish on a phone. A native modal <dialog> traps focus and
 * closes on Escape.
 * @returns {MoveDialogView}
 */
export function MoveDialog() {
  const dialog = document.createElement("dialog");
  dialog.className = "move-dialog";
  dialog.setAttribute("aria-labelledby", "move-dialog-title");

  /** @type {() => void} */
  let onClose = () => {};
  // The close event lands after a pick has already moved the dish (and
  // placed focus), so a pick must not also run onClose.
  let picked = false;
  dialog.addEventListener("close", () => {
    if (!picked) {
      onClose();
    }
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.close();
    }
  });

  return {
    element: dialog,
    open(request) {
      onClose = request.onClose;
      picked = false;
      const { dish } = request;

      const head = document.createElement("div");
      head.className = "move-dialog__head";
      const titles = document.createElement("div");
      titles.className = "move-dialog__titles";
      const kicker = document.createElement("div");
      kicker.className = "picker__kicker";
      kicker.textContent = "Move to…";
      const title = document.createElement("h2");
      title.className = "move-dialog__title";
      title.id = "move-dialog-title";
      title.textContent = displayTitle(dish.display);
      titles.append(kicker, title);
      const close = document.createElement("button");
      close.type = "button";
      close.className = "picker__close";
      close.textContent = "×";
      close.setAttribute("aria-label", "Close");
      close.addEventListener("click", () => dialog.close());
      head.append(titles, close);

      const list = document.createElement("div");
      list.className = "move-dialog__days";
      list.append(
        ...request.days.map((day) => {
          const row = document.createElement("div");
          row.className = "move-dialog__day";
          row.setAttribute("role", "group");
          row.setAttribute("aria-label", day.full);
          const name = document.createElement("span");
          name.className = "move-dialog__name";
          const weekday = document.createElement("b");
          weekday.textContent = day.weekday;
          name.append(weekday, ` ${day.dayMonth}`);
          row.append(
            name,
            ...MEAL_SLOTS.map((meal) => slotButton(dish, day, meal, () => {
              picked = true;
              dialog.close();
              request.onMove(day, meal);
            })),
          );
          return row;
        }),
      );

      dialog.replaceChildren(head, list);
      dialog.showModal();
      const first = list.querySelector("button:not(:disabled)");
      if (first instanceof HTMLElement) {
        first.focus();
      }
    },
  };
}

/**
 * One target slot. The dish's own slot, and any slot already holding the
 * same recipe (one row per recipe, D34), are shown but disabled.
 * @param {Dish} dish
 * @param {PlanDay} day
 * @param {MealSlot} meal
 * @param {() => void} onPick
 * @returns {HTMLButtonElement}
 */
function slotButton(dish, day, meal, onPick) {
  const from = dish.plannedMeal;
  const here = from.day === day.iso && from.meal === meal;
  const taken =
    !here && day.dishes[meal].some((d) => d.plannedMeal.recipe_code === from.recipe_code);

  const button = document.createElement("button");
  button.type = "button";
  button.className = "move-dialog__slot";
  button.disabled = here || taken;
  const note = here ? " \u00b7 here" : taken ? " \u00b7 already there" : "";
  button.textContent = `${SLOT_LABEL[meal]}${note}`;
  button.setAttribute(
    "aria-label",
    `${SLOT_LABEL[meal]}, ${day.full}${here ? ", where it is now" : taken ? ", already planned there" : ""}`,
  );
  const count = day.dishes[meal].length;
  if (!here && !taken && count > 0) {
    button.title = `${count} ${count === 1 ? "dish" : "dishes"} there already`;
  }
  button.addEventListener("click", onPick);
  return button;
}
