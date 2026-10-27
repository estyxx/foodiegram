// @ts-check

import {
  addMeal,
  createRecipe,
  deleteMeal,
  getPlan,
  getRecipe,
  updateMeal,
} from "../api/client.js";
import { BalanceBar, BalanceStrip } from "../components/Balance.js";
import { CustomRecipeDialog } from "../components/CustomRecipeDialog.js";
import { DayView } from "../components/DayView.js";
import { RecipePicker } from "../components/RecipePicker.js";
import { SLOT_LABEL, WeekBoard } from "../components/WeekBoard.js";
import {
  displayTitle,
  formatDayMonth,
  formatFullDay,
  formatWeekRange,
  formatWeekday,
} from "../lib/format.js";
import { indexedRecipe, loadRecipeIndex } from "../lib/recipeIndex.js";
import { DEFAULT_PORTIONS, addDays, isoDate, mondayOf, weekDays } from "../lib/week.js";

/** @typedef {import("../api/client.js").PlanResponse} PlanResponse */
/** @typedef {import("../api/client.js").PlannedMeal} PlannedMeal */
/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */
/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */
/** @typedef {import("../api/client.js").RecipeIndex} RecipeIndex */
/** @typedef {import("../components/DishCard.js").Dish} Dish */
/** @typedef {import("../components/DishCard.js").MealDisplay} MealDisplay */
/** @typedef {import("../components/WeekBoard.js").PlanDay} PlanDay */
/** @typedef {import("../lib/week.js").MealSlot} MealSlot */

const WEEK_STEP_DAYS = 7;
// D33: Monday-Friday by default, Saturday-Sunday on request; the week is
// still Monday-anchored and the balance always counts all seven days.
const WEEKDAYS = 5;
const WEEK_DAYS = 7;
const WEEKEND_KEY = "dispensa.plan.showWeekend";
// Desktop and mobile are two layouts over one state, not one reflowing grid.
const DESKTOP_QUERY = "(min-width: 760px)";

/**
 * Which slot the picker is filling, and the dish it swaps when "Change"
 * opened it.
 * @typedef {object} PickerTarget
 * @property {PlanDay} day
 * @property {MealSlot} meal
 * @property {PlannedMeal | null} replacing
 * @property {string} returnFocus Focus key of the control that opened it.
 */

/**
 * Render the plan view (#plan): a toolbar, the week's balance kept in view,
 * and the week as a meals-by-days board on desktop or one day at a time on
 * mobile (PLAN.md 11.9). Adding and changing dishes goes through one picker.
 * @param {HTMLElement} container
 * @returns {Promise<void>}
 */
export async function renderPlan(container) {
  container.replaceChildren();

  let weekStart = mondayOf(new Date());
  const today = isoDate(new Date());
  /** @type {PlanResponse | null} */
  let plan = null;
  /**
   * Displays the session index cannot supply: recipes saved after it loaded
   * (e.g. a custom recipe Claude just slotted).
   * @type {Map<string, MealDisplay>}
   */
  const recipesByCode = new Map();
  /** @type {RecipeIndex | null} */
  let index = null;
  let error = "";
  let showWeekend = readShowWeekend();
  const desktop = window.matchMedia(DESKTOP_QUERY);
  // Mobile shows today first; Monday when today is in another week.
  let selectedDay = Math.max(0, weekDays(weekStart).indexOf(today));
  let balanceOpen = false;
  /** @type {string | null} The "day-meal-index" whose ⋯ menu is open. */
  let openMenu = null;
  /** @type {PickerTarget | null} */
  let picker = null;
  /** @type {string | null} Where focus goes after the next render. */
  let pendingFocus = null;

  const root = document.createElement("div");
  root.className = "plan";

  const live = document.createElement("div");
  live.className = "visually-hidden";
  live.setAttribute("aria-live", "polite");

  const toolbar = document.createElement("div");
  toolbar.className = "plan__toolbar";

  const title = document.createElement("h1");
  title.className = "plan__title";
  title.textContent = "Plan the week";

  const controls = document.createElement("div");
  controls.className = "plan__controls";

  const stepper = document.createElement("div");
  stepper.className = "week-stepper";
  stepper.setAttribute("role", "group");
  stepper.setAttribute("aria-label", "Week");
  const range = document.createElement("span");
  range.className = "week-stepper__range";
  range.setAttribute("aria-live", "polite");
  stepper.append(
    stepButton("‹", "Previous week", () => void changeWeek(-WEEK_STEP_DAYS)),
    range,
    stepButton("›", "Next week", () => void changeWeek(WEEK_STEP_DAYS)),
  );

  const thisWeek = document.createElement("button");
  thisWeek.type = "button";
  thisWeek.className = "plan__this-week";
  thisWeek.textContent = "This week";
  thisWeek.addEventListener("click", () => {
    pendingFocus = "week-next";
    void goToWeek(mondayOf(new Date()));
  });

  const weekendSwitch = document.createElement("button");
  weekendSwitch.type = "button";
  weekendSwitch.className = "weekend-switch";
  weekendSwitch.setAttribute("role", "switch");
  const track = document.createElement("span");
  track.className = "weekend-switch__track";
  track.setAttribute("aria-hidden", "true");
  const knob = document.createElement("span");
  knob.className = "weekend-switch__knob";
  track.append(knob);
  const weekendLabel = document.createElement("span");
  weekendSwitch.append(track, weekendLabel);
  weekendSwitch.addEventListener("click", () => {
    showWeekend = !showWeekend;
    saveShowWeekend(showWeekend);
    renderAll();
  });

  controls.append(stepper, thisWeek, weekendSwitch);
  toolbar.append(title, controls);

  const errorMsg = document.createElement("p");
  errorMsg.className = "state-msg state-msg--error";
  errorMsg.setAttribute("role", "alert");
  errorMsg.hidden = true;

  const loading = document.createElement("p");
  loading.className = "state-msg";
  loading.textContent = "Loading your week…";

  const strip = BalanceStrip();
  const bar = BalanceBar(() => {
    balanceOpen = !balanceOpen;
    renderAll();
  });

  const dishHandlers = {
    onPortions: handlePortionsChange,
    onChange: (/** @type {Dish} */ dish) => {
      const day = shownDays().find((d) => d.iso === dish.plannedMeal.day);
      if (day) {
        openPicker(day, dish.plannedMeal.meal, dish.plannedMeal, `change-${dish.key}`);
      }
    },
    onRemove: handleRemove,
    onToggleMenu: (/** @type {string} */ key) => {
      openMenu = openMenu === key ? null : key;
      renderAll();
    },
    onAdd: (/** @type {PlanDay} */ day, /** @type {MealSlot} */ meal) =>
      openPicker(day, meal, null, `add-${day.iso}-${meal}`),
  };
  const board = WeekBoard(dishHandlers);
  const dayView = DayView({
    ...dishHandlers,
    onSelect: (position) => {
      selectedDay = position;
      openMenu = null;
      pendingFocus = "tab-selected";
      renderAll();
    },
  });

  const customDialog = CustomRecipeDialog();
  const recipePicker = RecipePicker({
    onPick: (recipe) => void handlePick(recipe),
    onCustom: (base) => void handleCustom(base),
    onClose: () => {
      const target = picker;
      picker = null;
      if (target !== null) {
        pendingFocus = target.returnFocus;
        renderAll();
      }
    },
  });

  root.append(
    live,
    toolbar,
    errorMsg,
    loading,
    strip.element,
    bar.element,
    board.element,
    dayView.element,
    recipePicker.element,
    customDialog.element,
  );
  container.append(root);

  const onLayoutChange = () => {
    // The view outlives nothing: once the router swaps it out, stop listening.
    if (!root.isConnected) {
      desktop.removeEventListener("change", onLayoutChange);
      return;
    }
    openMenu = null;
    renderAll();
  };
  desktop.addEventListener("change", onLayoutChange);

  /**
   * @param {string} code
   * @returns {MealDisplay}
   */
  function pickDisplay(code) {
    const known = recipesByCode.get(code) ?? (index ? indexedRecipe(index, code) : undefined);
    if (known) {
      return known;
    }
    // Rendered before hydration lands; the card fills in once it does.
    return {
      code,
      title: null,
      author_username: null,
      thumbnail_url: null,
      cloudinary_url: null,
      category_servings: [],
    };
  }

  /**
   * @param {RecipeDetail} recipe
   */
  function rememberDetail(recipe) {
    recipesByCode.set(recipe.code, {
      code: recipe.code,
      title: recipe.title,
      author_username: recipe.author_username,
      thumbnail_url: recipe.thumbnail_url,
      cloudinary_url: recipe.cloudinary_url,
      category_servings: recipe.mediterranean_categories.map((serving) => ({
        category: serving.category,
        servings: serving.servings,
      })),
    });
  }

  /**
   * @param {PlannedMeal[]} meals
   */
  async function hydrateDisplays(meals) {
    // The session index covers almost every meal; only codes it lacks cost a
    // full-recipe fetch.
    const missing = [...new Set(meals.map((meal) => meal.recipe_code))].filter(
      (code) => !recipesByCode.has(code) && !(index && indexedRecipe(index, code)),
    );
    if (missing.length === 0) {
      return;
    }
    const fetched = await Promise.all(missing.map((code) => getRecipe(code)));
    for (const recipe of fetched) {
      rememberDetail(recipe);
    }
  }

  /**
   * The days on screen: Monday-Friday, or the full week with the weekend on.
   * @returns {PlanDay[]}
   */
  function shownDays() {
    const meals = plan?.meals ?? [];
    return weekDays(weekStart)
      .slice(0, showWeekend ? WEEK_DAYS : WEEKDAYS)
      .map((iso) => ({
        iso,
        weekday: formatWeekday(iso),
        dayMonth: formatDayMonth(iso),
        full: formatFullDay(iso),
        dayNumber: Number(iso.slice(8)),
        isToday: iso === today,
        dishes: {
          lunch: dishesFor(meals, iso, "lunch"),
          dinner: dishesFor(meals, iso, "dinner"),
        },
      }));
  }

  /**
   * @param {PlannedMeal[]} meals
   * @param {string} day
   * @param {MealSlot} meal
   * @returns {Dish[]}
   */
  function dishesFor(meals, day, meal) {
    return meals
      .filter((m) => m.day === day && m.meal === meal)
      .map((plannedMeal, position) => ({
        plannedMeal,
        display: pickDisplay(plannedMeal.recipe_code),
        key: `${day}-${meal}-${position}`,
      }));
  }

  function renderAll() {
    const focusKey = pendingFocus ?? activeFocusKey();
    pendingFocus = null;

    loading.hidden = plan !== null;
    errorMsg.hidden = error === "";
    errorMsg.textContent = error;

    const isDesktop = desktop.matches;
    const ready = plan !== null;
    strip.element.hidden = !ready || !isDesktop;
    board.element.hidden = !ready || !isDesktop;
    bar.element.hidden = !ready || isDesktop;
    dayView.element.hidden = !ready || isDesktop;

    const days = shownDays();
    range.textContent = formatWeekRange(weekStart, days[days.length - 1].iso);
    thisWeek.hidden = weekStart === mondayOf(new Date());
    renderWeekendSwitch();

    if (plan !== null) {
      if (isDesktop) {
        strip.render(plan.balance);
        board.render(days, openMenu);
      } else {
        // A hidden weekend moves a Saturday/Sunday selection to Friday.
        selectedDay = Math.min(selectedDay, days.length - 1);
        bar.render(plan.balance, balanceOpen);
        dayView.render(days, selectedDay);
      }
      if (picker !== null) {
        recipePicker.update(pickerContext(picker));
      }
    }

    restoreFocus(focusKey);
  }

  /**
   * The balance counts weekend dishes even while they are hidden, so the
   * switch says how many there are rather than hiding them silently.
   */
  function renderWeekendSwitch() {
    const weekend = new Set(weekDays(weekStart).slice(WEEKDAYS));
    const count = (plan?.meals ?? []).filter((meal) => weekend.has(meal.day)).length;
    weekendLabel.textContent = count > 0 && !showWeekend ? `Weekend · ${count}` : "Weekend";
    weekendSwitch.setAttribute("aria-checked", String(showWeekend));
    weekendSwitch.setAttribute(
      "aria-label",
      count > 0 && !showWeekend
        ? `Weekend, ${count} ${count === 1 ? "dish" : "dishes"} planned`
        : "Weekend",
    );
  }

  /**
   * Re-renders replace the board's buttons, so focus is carried across by key.
   * @param {string | null} key
   */
  function restoreFocus(key) {
    if (key === null || recipePicker.isOpen()) {
      return;
    }
    const target = root.querySelector(`[data-focus-key="${CSS.escape(key)}"]`);
    if (target instanceof HTMLElement && target.offsetParent !== null) {
      target.focus();
    }
  }

  /**
   * @returns {string | null}
   */
  function activeFocusKey() {
    const active = document.activeElement;
    return active instanceof HTMLElement && root.contains(active)
      ? (active.dataset.focusKey ?? null)
      : null;
  }

  /**
   * @param {string} text
   */
  function announce(text) {
    // Clear first so the same sentence twice is still read twice.
    live.textContent = "";
    window.setTimeout(() => {
      live.textContent = text;
    }, 50);
  }

  /**
   * @param {PlanDay} day
   * @param {MealSlot} meal
   * @param {PlannedMeal | null} replacing
   * @param {string} returnFocus
   */
  function openPicker(day, meal, replacing, returnFocus) {
    if (plan === null) {
      return;
    }
    picker = { day, meal, replacing, returnFocus };
    openMenu = null;
    renderAll();
    recipePicker.open(pickerContext(picker));
  }

  /**
   * @param {PickerTarget} target
   * @returns {import("../components/RecipePicker.js").PickerContext}
   */
  function pickerContext(target) {
    const inSlot = (plan?.meals ?? []).filter(
      (m) => m.day === target.day.iso && m.meal === target.meal,
    );
    return {
      kicker: `${target.day.weekday} ${target.day.dayMonth} · ${SLOT_LABEL[target.meal]}`,
      replacing: target.replacing !== null,
      current: inSlot.map((m) => displayTitle(pickDisplay(m.recipe_code))),
      inSlot: new Set(inSlot.map((m) => m.recipe_code)),
      balance: plan?.balance ?? [],
      index,
    };
  }

  /**
   * Add mode appends and keeps the picker open for more; change mode swaps
   * the dish, keeps its servings, and closes.
   * @param {RecipeSummary} recipe
   */
  async function handlePick(recipe) {
    const target = picker;
    if (target === null) {
      return;
    }
    if (target.replacing !== null) {
      recipePicker.close();
      await handleReplace(target.replacing, recipe);
      announce(`Changed to ${displayTitle(recipe)}. Balance updated.`);
      return;
    }
    recipePicker.noteAdded();
    await handleAdd(target.day.iso, target.meal, recipe);
    announce(
      `${displayTitle(recipe)} added to ${target.day.weekday} ${target.meal}. Balance updated.`,
    );
  }

  /**
   * "My version of…" a recipe, or one written from scratch: save it as a
   * MANUAL recipe (D23), then add it to the picker's slot — or swap it in for
   * the dish whose "Change" opened the picker.
   * @param {RecipeSummary | null} base
   */
  async function handleCustom(base) {
    const target = picker;
    if (plan === null || target === null) {
      return;
    }
    /** @type {RecipeDetail | null} */
    let detail = null;
    if (base !== null) {
      try {
        detail = await getRecipe(base.code);
      } catch {
        error = "Couldn't open that recipe — try again.";
        renderAll();
        return;
      }
    }
    /** @type {RecipeDetail | null} Kept across retries so a retry never saves twice. */
    let created = null;
    const saved = await customDialog.open({
      base: detail,
      slotLabel: `${target.day.weekday} ${target.day.dayMonth} · ${SLOT_LABEL[target.meal]}`,
      onSave: async (draft) => {
        created ??= await createRecipe(draft);
        rememberDetail(created);
        plan =
          target.replacing?.id != null
            ? await updateMeal(weekStart, target.replacing.id, {
                recipe_code: created.code,
                portions: target.replacing.portions,
              })
            : await addMeal(weekStart, {
                day: target.day.iso,
                meal: target.meal,
                recipe_code: created.code,
                portions: DEFAULT_PORTIONS,
              });
        error = "";
        renderAll();
      },
    });
    if (saved && created !== null) {
      recipePicker.close();
      announce(`${displayTitle(created)} saved and planned. Balance updated.`);
    }
  }

  /**
   * @param {string} next
   */
  async function goToWeek(next) {
    if (next === weekStart && plan !== null) {
      return;
    }
    weekStart = next;
    plan = null;
    error = "";
    openMenu = null;
    renderAll();
    try {
      const [fetched, loadedIndex] = await Promise.all([
        getPlan(weekStart),
        // A failed index load only costs the per-meal fallback fetches.
        loadRecipeIndex().catch(() => null),
      ]);
      index = loadedIndex;
      await hydrateDisplays(fetched.meals);
      plan = fetched;
    } catch {
      error = "Couldn't load this week's plan — try again.";
    }
    renderAll();
  }

  /**
   * @param {number} deltaDays
   */
  function changeWeek(deltaDays) {
    return goToWeek(addDays(weekStart, deltaDays));
  }

  /**
   * Add a dish to the slot, beside any already there (D34).
   * @param {string} day
   * @param {MealSlot} meal
   * @param {RecipeSummary} recipe
   */
  async function handleAdd(day, meal, recipe) {
    if (plan === null) {
      return;
    }
    const previous = plan;
    // The server keeps one row per recipe per slot, so a repeat add shows nothing new.
    const already = plan.meals.some(
      (m) => m.day === day && m.meal === meal && m.recipe_code === recipe.code,
    );
    if (!already) {
      plan = {
        ...plan,
        meals: [
          ...plan.meals,
          { id: null, day, meal, recipe_code: recipe.code, portions: DEFAULT_PORTIONS },
        ],
      };
    }
    error = "";
    renderAll();
    try {
      plan = await addMeal(weekStart, { day, meal, recipe_code: recipe.code, portions: DEFAULT_PORTIONS });
    } catch {
      plan = previous;
      error = "Couldn't save that meal — try again.";
    }
    renderAll();
  }

  /**
   * Swap a dish for another recipe, keeping its servings.
   * @param {PlannedMeal} plannedMeal
   * @param {RecipeSummary} recipe
   */
  async function handleReplace(plannedMeal, recipe) {
    // Same mid-flight race as handleRemove: no id yet, nothing to target.
    if (plan === null || plannedMeal.id === null) {
      return;
    }
    const previous = plan;
    const id = plannedMeal.id;
    plan = {
      ...plan,
      meals: plan.meals.map((m) => (m.id === id ? { ...m, recipe_code: recipe.code } : m)),
    };
    error = "";
    renderAll();
    try {
      plan = await updateMeal(weekStart, id, {
        recipe_code: recipe.code,
        portions: plannedMeal.portions,
      });
    } catch {
      plan = previous;
      error = "Couldn't change that meal — is it already in this slot?";
    }
    renderAll();
  }

  /**
   * @param {PlannedMeal} plannedMeal
   * @param {number} portions
   */
  async function handlePortionsChange(plannedMeal, portions) {
    if (plan === null || plannedMeal.id === null || portions === plannedMeal.portions) {
      return;
    }
    const previous = plan;
    const id = plannedMeal.id;
    plan = {
      ...plan,
      meals: plan.meals.map((m) => (m.id === id ? { ...m, portions } : m)),
    };
    renderAll();
    try {
      plan = await updateMeal(weekStart, id, {
        recipe_code: plannedMeal.recipe_code,
        portions,
      });
    } catch {
      plan = previous;
      error = "Couldn't update portions — try again.";
    }
    renderAll();
  }

  /**
   * @param {Dish} dish
   */
  async function handleRemove(dish) {
    const { plannedMeal } = dish;
    // A meal added moments ago may not have its server id back yet; removing
    // mid-flight is a rare enough race to skip rather than build a request
    // queue for.
    if (plan === null || plannedMeal.id === null) {
      return;
    }
    const previous = plan;
    const id = plannedMeal.id;
    plan = { ...plan, meals: plan.meals.filter((m) => m.id !== id) };
    openMenu = null;
    // The removed card's buttons are gone; the slot's add button is the
    // nearest thing left.
    pendingFocus = `add-${plannedMeal.day}-${plannedMeal.meal}`;
    renderAll();
    announce(`${displayTitle(dish.display)} removed. Balance updated.`);
    try {
      plan = await deleteMeal(weekStart, id);
    } catch {
      plan = previous;
      error = "Couldn't remove that meal — try again.";
    }
    renderAll();
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
    button.className = "week-stepper__btn";
    button.textContent = glyph;
    button.dataset.focusKey = label === "Previous week" ? "week-prev" : "week-next";
    button.setAttribute("aria-label", label);
    button.addEventListener("click", onClick);
    return button;
  }

  await goToWeek(weekStart);
}

/**
 * Whether this browser last chose to see the weekend. A per-viewer
 * convenience only, so any storage failure just means "no".
 * @returns {boolean}
 */
function readShowWeekend() {
  try {
    return window.localStorage.getItem(WEEKEND_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * @param {boolean} show
 */
function saveShowWeekend(show) {
  try {
    window.localStorage.setItem(WEEKEND_KEY, show ? "1" : "0");
  } catch {
    // Private mode or blocked storage: the switch still works for this visit.
  }
}
