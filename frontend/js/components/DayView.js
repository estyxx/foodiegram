// @ts-check

import { MobileDishCard } from "./DishCard.js";
import { SLOT_LABEL, todayPill } from "./WeekBoard.js";
import { MEAL_SLOTS } from "../lib/week.js";

/** @typedef {import("../lib/week.js").MealSlot} MealSlot */
/** @typedef {import("./WeekBoard.js").PlanDay} PlanDay */
/** @typedef {import("./WeekBoard.js").BoardHandlers} BoardHandlers */

/**
 * @typedef {BoardHandlers & {
 *   onSelect: (index: number) => void,
 * }} DayViewHandlers
 */

/**
 * @typedef {object} DayViewView
 * @property {HTMLElement} element
 * @property {(days: PlanDay[], selected: number) => void} render
 */

/**
 * Mobile: one day at a time. A strip of day tabs (two dots each: lunch,
 * dinner) picks the day; its lunch and dinner sit below, then prev/next.
 * @param {DayViewHandlers} handlers
 * @returns {DayViewView}
 */
export function DayView(handlers) {
  const wrap = document.createElement("div");
  wrap.className = "day-view";

  return {
    element: wrap,
    render(days, selected) {
      const day = days[selected];
      const panelId = "day-view-panel";

      const tabs = document.createElement("div");
      tabs.className = "day-tabs";
      tabs.setAttribute("role", "tablist");
      tabs.setAttribute("aria-label", "Days");
      tabs.style.setProperty("--days", String(days.length));
      tabs.append(...days.map((d, index) => dayTab(d, index === selected, index, panelId, handlers)));
      tabs.addEventListener("keydown", (event) => {
        // Arrow keys move between tabs, as the tablist pattern expects.
        const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
        if (step !== 0) {
          event.preventDefault();
          handlers.onSelect((selected + step + days.length) % days.length);
        }
      });

      const panel = document.createElement("div");
      panel.id = panelId;
      panel.setAttribute("role", "tabpanel");
      panel.setAttribute("aria-label", day.full);

      const heading = document.createElement("div");
      heading.className = "day-view__heading";
      const title = document.createElement("h2");
      title.className = "day-view__title";
      title.textContent = day.full;
      heading.append(title);
      if (day.isToday) {
        heading.append(todayPill());
      }
      panel.append(heading, ...MEAL_SLOTS.map((meal) => mealSection(day, meal, handlers)));

      const pager = document.createElement("div");
      pager.className = "day-view__pager";
      const prev = (selected - 1 + days.length) % days.length;
      const next = (selected + 1) % days.length;
      pager.append(
        pagerButton(`← ${days[prev].weekday}`, `Previous day, ${days[prev].full}`, () =>
          handlers.onSelect(prev),
        ),
        pagerButton(`${days[next].weekday} →`, `Next day, ${days[next].full}`, () =>
          handlers.onSelect(next),
        ),
      );
      pager.children[0].setAttribute("data-focus-key", "day-prev");
      pager.children[1].setAttribute("data-focus-key", "day-next");

      wrap.replaceChildren(tabs, panel, pager);
    },
  };
}

/**
 * @param {PlanDay} day
 * @param {boolean} isSelected
 * @param {number} index
 * @param {string} panelId
 * @param {DayViewHandlers} handlers
 * @returns {HTMLButtonElement}
 */
function dayTab(day, isSelected, index, panelId, handlers) {
  const tab = document.createElement("button");
  tab.type = "button";
  tab.className = "day-tab";
  tab.classList.toggle("day-tab--selected", isSelected);
  tab.classList.toggle("day-tab--today", day.isToday);
  tab.setAttribute("role", "tab");
  tab.setAttribute("aria-selected", String(isSelected));
  tab.setAttribute("aria-controls", panelId);
  tab.tabIndex = isSelected ? 0 : -1;
  tab.dataset.focusKey = `tab-${isSelected ? "selected" : day.iso}`;
  const open = MEAL_SLOTS.filter((meal) => day.dishes[meal].length === 0).map(
    (meal) => ` · ${meal} open`,
  );
  tab.setAttribute("aria-label", `${day.full}${open.join("")}`);
  tab.addEventListener("click", () => handlers.onSelect(index));

  const name = document.createElement("span");
  name.className = "day-tab__name";
  name.textContent = day.weekday;
  const number = document.createElement("span");
  number.className = "day-tab__number";
  number.textContent = String(day.dayNumber);
  const dots = document.createElement("span");
  dots.className = "day-tab__dots";
  dots.append(
    ...MEAL_SLOTS.map((meal) => {
      const dot = document.createElement("span");
      dot.className = "day-tab__dot";
      dot.classList.toggle("day-tab__dot--empty", day.dishes[meal].length === 0);
      return dot;
    }),
  );
  tab.append(name, number, dots);
  return tab;
}

/**
 * @param {PlanDay} day
 * @param {MealSlot} meal
 * @param {DayViewHandlers} handlers
 * @returns {HTMLElement}
 */
function mealSection(day, meal, handlers) {
  const dishes = day.dishes[meal];
  const section = document.createElement("section");
  section.className = "day-meal";
  section.setAttribute("aria-label", SLOT_LABEL[meal]);

  const head = document.createElement("div");
  head.className = "day-meal__head";
  const label = document.createElement("span");
  label.className = "day-meal__label";
  label.textContent = SLOT_LABEL[meal];
  const count = document.createElement("span");
  count.className = "day-meal__count";
  count.textContent =
    dishes.length === 0 ? "open" : `${dishes.length} ${dishes.length === 1 ? "dish" : "dishes"}`;
  head.append(label, count);

  const list = document.createElement("div");
  list.className = "day-meal__list";
  list.append(...dishes.map((dish) => MobileDishCard(dish, handlers)));

  const add = document.createElement("button");
  add.type = "button";
  add.className = "add-dish add-dish--mobile";
  add.textContent =
    dishes.length > 0 ? "+ Add another dish" : `+ Add ${SLOT_LABEL[meal].toLowerCase()}`;
  add.dataset.focusKey = `add-${day.iso}-${meal}`;
  add.addEventListener("click", () => handlers.onAdd(day, meal));
  list.append(add);

  section.append(head, list);
  return section;
}

/**
 * @param {string} text
 * @param {string} label
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function pagerButton(text, label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "day-view__page";
  button.textContent = text;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", onClick);
  return button;
}
