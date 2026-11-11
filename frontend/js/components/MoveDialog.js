// @ts-check

import { SLOT_LABEL } from "./WeekBoard.js";
import { displayTitle, formatWeekRange } from "../lib/format.js";
import { MEAL_SLOTS, addDays } from "../lib/week.js";

/** @typedef {import("../lib/week.js").MealSlot} MealSlot */
/** @typedef {import("./DishCard.js").Dish} Dish */
/** @typedef {import("./WeekBoard.js").PlanDay} PlanDay */

const WEEK_STEP_DAYS = 7;

/**
 * @typedef {object} MoveRequest
 * @property {Dish} dish
 * @property {string} weekStart The week to show first (the dish's own).
 * @property {(weekStart: string) => Promise<PlanDay[]>} loadWeek All seven
 *   days of a week, with the dishes already planned there.
 * @property {(day: PlanDay, meal: MealSlot) => void} onMove
 * @property {() => void} onClose Fires when it closes without a move.
 */

/**
 * @typedef {object} MoveDialogView
 * @property {HTMLDialogElement} element
 * @property {(request: MoveRequest) => void} open
 */

/**
 * "Move to…": every lunch and dinner of a week as a button, with a week
 * stepper to reach earlier and later weeks. The menu path for what drag and
 * drop does on the desktop board (PLAN §15.6), and the only way to move a
 * dish on a phone. A native modal <dialog> traps focus and closes on Escape.
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
      let shownWeek = request.weekStart;
      // A slow week fetch must not overwrite a newer one.
      let latest = 0;

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

      const stepper = document.createElement("div");
      stepper.className = "week-stepper move-dialog__weeks";
      stepper.setAttribute("role", "group");
      stepper.setAttribute("aria-label", "Week");
      const range = document.createElement("span");
      range.className = "week-stepper__range";
      range.setAttribute("aria-live", "polite");
      stepper.append(
        weekButton("‹", "Previous week", () => void showWeek(-WEEK_STEP_DAYS)),
        range,
        weekButton("›", "Next week", () => void showWeek(WEEK_STEP_DAYS)),
      );

      const list = document.createElement("div");
      list.className = "move-dialog__days";

      /**
       * @param {number} deltaDays
       */
      async function showWeek(deltaDays) {
        shownWeek = addDays(shownWeek, deltaDays);
        const ticket = (latest += 1);
        range.textContent = formatWeekRange(shownWeek, addDays(shownWeek, 6));
        list.replaceChildren(note("Loading…"));
        try {
          const days = await request.loadWeek(shownWeek);
          if (ticket === latest) {
            renderDays(days);
          }
        } catch {
          if (ticket === latest) {
            list.replaceChildren(note("Couldn't load that week — try again."));
          }
        }
      }

      /**
       * @param {PlanDay[]} days
       */
      function renderDays(days) {
        list.replaceChildren(
          ...days.map((day) => {
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
              ...MEAL_SLOTS.map((meal) =>
                slotButton(dish, day, meal, () => {
                  picked = true;
                  dialog.close();
                  request.onMove(day, meal);
                }),
              ),
            );
            return row;
          }),
        );
      }

      dialog.replaceChildren(head, stepper, list);
      dialog.showModal();
      void showWeek(0).then(() => {
        const first = list.querySelector("button:not(:disabled)");
        if (first instanceof HTMLElement && dialog.open) {
          first.focus();
        }
      });
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
  const note = here ? " · here" : taken ? " · already there" : "";
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

/**
 * @param {string} glyph
 * @param {string} label
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function weekButton(glyph, label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "week-stepper__btn";
  button.textContent = glyph;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", onClick);
  return button;
}

/**
 * @param {string} text
 * @returns {HTMLElement}
 */
function note(text) {
  const row = document.createElement("p");
  row.className = "move-dialog__note";
  row.textContent = text;
  return row;
}
