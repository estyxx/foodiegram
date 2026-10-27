// @ts-check

import { DishCard } from "./DishCard.js";
import { MEAL_SLOTS } from "../lib/week.js";

/** @typedef {import("../lib/week.js").MealSlot} MealSlot */
/** @typedef {import("./DishCard.js").Dish} Dish */
/** @typedef {import("./DishCard.js").DishHandlers} DishHandlers */

/** @type {Record<MealSlot, string>} */
export const SLOT_LABEL = { lunch: "Lunch", dinner: "Dinner" };

/**
 * One day of the shown week, ready to draw.
 * @typedef {object} PlanDay
 * @property {string} iso ISO date.
 * @property {string} weekday "MAR".
 * @property {string} dayMonth "27 ott".
 * @property {string} full "Martedì 27 ottobre".
 * @property {number} dayNumber 27.
 * @property {boolean} isToday
 * @property {Record<MealSlot, Dish[]>} dishes
 */

/**
 * @typedef {DishHandlers & {
 *   onAdd: (day: PlanDay, meal: MealSlot) => void,
 * }} BoardHandlers
 */

/**
 * @typedef {object} WeekBoardView
 * @property {HTMLElement} element
 * @property {(days: PlanDay[], openMenu: string | null) => void} render
 */

/**
 * Desktop: meals as rows and days as columns, so Tuesday's lunch sits beside
 * Wednesday's.
 * @param {BoardHandlers} handlers
 * @returns {WeekBoardView}
 */
export function WeekBoard(handlers) {
  const board = document.createElement("div");
  board.className = "week-board";

  return {
    element: board,
    render(days, openMenu) {
      board.style.setProperty("--days", String(days.length));
      const corner = document.createElement("div");
      /** @type {HTMLElement[]} */
      const cells = [corner, ...days.map(dayHeader)];
      for (const meal of MEAL_SLOTS) {
        const label = document.createElement("div");
        label.className = "week-board__slot";
        label.textContent = SLOT_LABEL[meal];
        cells.push(label, ...days.map((day) => buildCell(day, meal, openMenu, handlers)));
      }
      board.replaceChildren(...cells);
    },
  };
}

/**
 * @param {PlanDay} day
 * @returns {HTMLElement}
 */
function dayHeader(day) {
  const head = document.createElement("div");
  head.className = "week-board__day";
  head.classList.toggle("week-board__day--today", day.isToday);
  const name = document.createElement("b");
  name.textContent = day.weekday;
  const date = document.createElement("span");
  date.textContent = day.dayMonth;
  head.append(name, date);
  if (day.isToday) {
    head.append(todayPill());
  }
  return head;
}

/**
 * @returns {HTMLElement}
 */
export function todayPill() {
  const pill = document.createElement("span");
  pill.className = "today-pill";
  pill.textContent = "today";
  return pill;
}

/**
 * @param {PlanDay} day
 * @param {MealSlot} meal
 * @param {string | null} openMenu
 * @param {BoardHandlers} handlers
 * @returns {HTMLElement}
 */
function buildCell(day, meal, openMenu, handlers) {
  const cell = document.createElement("div");
  cell.className = "week-board__cell";
  cell.classList.toggle("week-board__cell--today", day.isToday);

  const dishes = day.dishes[meal];
  cell.append(...dishes.map((dish) => DishCard(dish, openMenu === dish.key, handlers)));

  const add = document.createElement("button");
  add.type = "button";
  add.className = "add-dish";
  add.classList.toggle("add-dish--more", dishes.length > 0);
  add.textContent = dishes.length > 0 ? "+ another" : "+ add";
  add.dataset.focusKey = `add-${day.iso}-${meal}`;
  add.setAttribute("aria-label", `Add a dish to ${day.weekday} ${day.dayMonth} ${SLOT_LABEL[meal]}`);
  add.addEventListener("click", () => handlers.onAdd(day, meal));
  cell.append(add);
  return cell;
}
