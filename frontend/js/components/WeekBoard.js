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
 *   onDrop: (dish: Dish, day: PlanDay, meal: MealSlot) => void,
 * }} BoardHandlers
 */

/** The drag payload type; other drags (files, links) never light a cell up. */
const DRAG_TYPE = "application/x-dispensa-dish";

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

  /**
   * The dish being dragged. dragover cannot read the payload, only its type,
   * so the board keeps the dish itself to tell which cells may take it.
   * @type {Dish | null}
   */
  let dragging = null;

  /** @type {DragHooks} */
  const drag = {
    start(dish, card, event) {
      dragging = dish;
      event.dataTransfer?.setData(DRAG_TYPE, dish.key);
      event.dataTransfer?.setData("text/plain", dish.display.title ?? dish.display.code);
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
      }
      board.classList.add("week-board--dragging");
      card.classList.add("dish-card--dragging");
    },
    end(card) {
      dragging = null;
      board.classList.remove("week-board--dragging");
      card.classList.remove("dish-card--dragging");
      for (const cell of board.querySelectorAll(".week-board__cell--drop")) {
        cell.classList.remove("week-board__cell--drop");
      }
    },
    accepts(day, meal) {
      if (dragging === null) {
        return false;
      }
      const from = dragging.plannedMeal;
      if (from.day === day.iso && from.meal === meal) {
        return false;
      }
      // A slot keeps one row per recipe (D34), so it cannot take a second copy.
      return !day.dishes[meal].some((d) => d.plannedMeal.recipe_code === from.recipe_code);
    },
    drop(day, meal) {
      const dish = dragging;
      const ok = dish !== null && drag.accepts(day, meal);
      // The move re-renders the board and the dragged card with it, and a
      // removed source gets no dragend, so tidy up here first.
      dragging = null;
      board.classList.remove("week-board--dragging");
      if (ok) {
        handlers.onDrop(dish, day, meal);
      }
    },
  };

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
        cells.push(label, ...days.map((day) => buildCell(day, meal, openMenu, handlers, drag)));
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
 * @typedef {object} DragHooks
 * @property {(dish: Dish, card: HTMLElement, event: DragEvent) => void} start
 * @property {(card: HTMLElement) => void} end
 * @property {(day: PlanDay, meal: MealSlot) => boolean} accepts
 * @property {(day: PlanDay, meal: MealSlot) => void} drop
 */

/**
 * @param {PlanDay} day
 * @param {MealSlot} meal
 * @param {string | null} openMenu
 * @param {BoardHandlers} handlers
 * @param {DragHooks} drag
 * @returns {HTMLElement}
 */
function buildCell(day, meal, openMenu, handlers, drag) {
  const cell = document.createElement("div");
  cell.className = "week-board__cell";
  cell.classList.toggle("week-board__cell--today", day.isToday);

  const dishes = day.dishes[meal];
  for (const dish of dishes) {
    const card = DishCard(dish, openMenu === dish.key, handlers);
    // A dish added moments ago has no server id yet, so nothing to move.
    if (dish.plannedMeal.id !== null) {
      card.draggable = true;
      card.addEventListener("dragstart", (event) => drag.start(dish, card, event));
      card.addEventListener("dragend", () => drag.end(card));
    }
    cell.append(card);
  }

  cell.addEventListener("dragover", (event) => {
    if (!event.dataTransfer?.types.includes(DRAG_TYPE) || !drag.accepts(day, meal)) {
      return;
    }
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    cell.classList.add("week-board__cell--drop");
  });
  cell.addEventListener("dragleave", (event) => {
    // Leaving for a child (a card inside the cell) is not leaving the cell.
    if (!(event.relatedTarget instanceof Node && cell.contains(event.relatedTarget))) {
      cell.classList.remove("week-board__cell--drop");
    }
  });
  cell.addEventListener("drop", (event) => {
    event.preventDefault();
    cell.classList.remove("week-board__cell--drop");
    drag.drop(day, meal);
  });

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
