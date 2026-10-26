// @ts-check

import { createRecipe, deleteMeal, getPlan, getRecipe, upsertMeal } from "../api/client.js";
import { BalancePanel } from "../components/BalancePanel.js";
import { CustomRecipeDialog } from "../components/CustomRecipeDialog.js";
import { DayColumn } from "../components/DayColumn.js";
import { emptyFilters } from "../lib/filters.js";
import { formatDayLabel, formatWeekRange } from "../lib/format.js";
import { searchLocally } from "../lib/localFilter.js";
import { indexedRecipe, loadRecipeIndex } from "../lib/recipeIndex.js";
import { addDays, isoDate, mondayOf, weekDays } from "../lib/week.js";

/** @typedef {import("../api/client.js").PlanResponse} PlanResponse */
/** @typedef {import("../api/client.js").PlannedMeal} PlannedMeal */
/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */
/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */
/** @typedef {import("../components/DayColumn.js").MealDisplay} MealDisplay */
/** @typedef {import("../lib/week.js").MealSlot} MealSlot */

const WEEK_STEP_DAYS = 7;
const SEARCH_LIMIT = 20;
// D33: Monday-Friday by default, Saturday-Sunday on request; the week is
// still Monday-anchored and the balance always counts all seven days.
const WEEKDAYS = 5;
const WEEK_DAYS = 7;
const WEEKEND_KEY = "dispensa.plan.showWeekend";
const DEFAULT_PORTIONS = 2;

/**
 * Render the plan view (#plan): a live BalancePanel above a Monday-Sunday
 * strip of DayColumns, per PLAN.md 4.4 and D19/D20's build order. The v1
 * slice stops here — the pantry-dependent #week home dashboard is Phase 5.
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
   * (e.g. a custom recipe Claude just slotted) and freshly added search hits.
   * @type {Map<string, MealDisplay>}
   */
  const recipesByCode = new Map();
  /** @type {import("../api/client.js").RecipeIndex | null} */
  let index = null;
  let error = "";
  let showWeekend = readShowWeekend();

  const header = document.createElement("header");
  header.className = "plan__header";

  const title = document.createElement("h1");
  title.className = "plan__title";
  title.textContent = "Plan the week";

  const range = document.createElement("p");
  range.className = "plan__range";
  range.setAttribute("aria-live", "polite");

  const nav = document.createElement("div");
  nav.className = "plan__nav";
  const weekendToggle = navButton("Show weekend", () => {
    showWeekend = !showWeekend;
    saveShowWeekend(showWeekend);
    renderAll();
  });
  nav.append(
    navButton("← Previous week", () => void changeWeek(-WEEK_STEP_DAYS)),
    navButton("This week", () => void goToWeek(mondayOf(new Date()))),
    navButton("Next week →", () => void changeWeek(WEEK_STEP_DAYS)),
    weekendToggle,
  );

  header.append(title, nav, range);

  const balancePanel = BalancePanel();

  const errorMsg = document.createElement("p");
  errorMsg.className = "state-msg state-msg--error";
  errorMsg.hidden = true;

  const loading = document.createElement("p");
  loading.className = "state-msg";
  loading.textContent = "Loading your week…";

  const grid = document.createElement("div");
  grid.className = "plan__grid";
  grid.hidden = true;

  const handlers = { onAdd: handleAdd, onPortionsChange: handlePortionsChange,
    onRemove: handleRemove, onSearch: handleSearch, onCustom: handleCustom };
  // All seven are built once; Saturday and Sunday are hidden unless asked for.
  const columns = weekDays(weekStart).map(() => DayColumn(handlers));
  grid.append(...columns.map((column) => column.element));

  const customDialog = CustomRecipeDialog();

  container.append(
    header,
    balancePanel.element,
    errorMsg,
    loading,
    grid,
    customDialog.element,
  );

  /**
   * @param {string} code
   * @returns {MealDisplay}
   */
  function pickDisplay(code) {
    const known = recipesByCode.get(code) ?? (index ? indexedRecipe(index, code) : undefined);
    if (known) {
      return known;
    }
    // Rendered before hydration lands; the row fills in once it does.
    return { code, title: null, author_username: null, thumbnail_url: null, cloudinary_url: null };
  }

  /**
   * @param {RecipeSummary | RecipeDetail} recipe
   */
  function rememberDisplay(recipe) {
    recipesByCode.set(recipe.code, {
      code: recipe.code,
      title: recipe.title,
      author_username: recipe.author_username,
      thumbnail_url: recipe.thumbnail_url,
      cloudinary_url: recipe.cloudinary_url,
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
      rememberDisplay(recipe);
    }
  }

  function renderAll() {
    loading.hidden = plan !== null;
    grid.hidden = plan === null;
    errorMsg.hidden = error === "";
    errorMsg.textContent = error;

    if (plan === null) {
      return;
    }

    const shown = showWeekend ? WEEK_DAYS : WEEKDAYS;
    range.textContent = formatWeekRange(weekStart, addDays(weekStart, shown - 1));
    balancePanel.render(plan.balance, plan.oily_fish);
    renderWeekendToggle();
    grid.classList.toggle("plan__grid--week", showWeekend);

    const mealsByDay = groupMeals(plan.meals);
    weekDays(weekStart).forEach((day, position) => {
      columns[position].element.hidden = position >= shown;
      columns[position].render({
        day,
        label: formatDayLabel(day),
        isToday: day === today,
        meals: mealsByDay.get(day) ?? {},
        resolve: pickDisplay,
        balance: plan?.balance ?? [],
        suggestions: plan?.suggestions ?? [],
      });
    });
  }

  /**
   * The balance counts weekend meals even while they are hidden, so the
   * toggle says how many there are rather than hiding them silently.
   */
  function renderWeekendToggle() {
    const weekend = new Set(weekDays(weekStart).slice(WEEKDAYS));
    const count = (plan?.meals ?? []).filter((meal) => weekend.has(meal.day)).length;
    const suffix = count > 0 ? ` \u00b7 ${count} ${count === 1 ? "meal" : "meals"}` : "";
    weekendToggle.textContent = `${showWeekend ? "Hide" : "Show"} weekend${suffix}`;
    weekendToggle.setAttribute("aria-pressed", String(showWeekend));
  }

  /**
   * "My version of…" a recipe, or one written from scratch: save it as a
   * MANUAL recipe (D23), then put it in the slot.
   * @param {string} day
   * @param {MealSlot} meal
   * @param {RecipeSummary | null} base
   * @returns {Promise<boolean>} True once saved and slotted.
   */
  async function handleCustom(day, meal, base) {
    if (plan === null) {
      return false;
    }
    /** @type {RecipeDetail | null} */
    let detail = null;
    if (base !== null) {
      try {
        detail = await getRecipe(base.code);
      } catch {
        error = "Couldn't open that recipe — try again.";
        renderAll();
        return false;
      }
    }
    /** @type {RecipeDetail | null} Kept across retries so a retry never saves twice. */
    let created = null;
    return customDialog.open({
      base: detail,
      slotLabel: `${formatDayLabel(day)} \u00b7 ${meal === "lunch" ? "Lunch" : "Dinner"}`,
      onSave: async (draft) => {
        created ??= await createRecipe(draft);
        rememberDisplay(created);
        plan = await upsertMeal(weekStart, {
          day,
          meal,
          recipe_code: created.code,
          portions: DEFAULT_PORTIONS,
        });
        error = "";
        renderAll();
      },
    });
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
   * @param {string} day
   * @param {MealSlot} meal
   * @param {RecipeSummary} recipe
   */
  async function handleAdd(day, meal, recipe) {
    if (plan === null) {
      return;
    }
    const previous = plan;
    rememberDisplay(recipe);
    plan = {
      ...plan,
      meals: [
        ...plan.meals.filter((m) => !(m.day === day && m.meal === meal)),
        { id: null, day, meal, recipe_code: recipe.code, portions: DEFAULT_PORTIONS },
      ],
    };
    error = "";
    renderAll();
    try {
      plan = await upsertMeal(weekStart, { day, meal, recipe_code: recipe.code, portions: DEFAULT_PORTIONS });
    } catch {
      plan = previous;
      error = "Couldn't save that meal — try again.";
    }
    renderAll();
  }

  /**
   * @param {PlannedMeal} plannedMeal
   * @param {number} portions
   */
  async function handlePortionsChange(plannedMeal, portions) {
    if (plan === null) {
      return;
    }
    const previous = plan;
    plan = {
      ...plan,
      meals: plan.meals.map((m) =>
        m.day === plannedMeal.day && m.meal === plannedMeal.meal ? { ...m, portions } : m,
      ),
    };
    renderAll();
    try {
      plan = await upsertMeal(weekStart, {
        day: plannedMeal.day,
        meal: plannedMeal.meal,
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
   * @param {PlannedMeal} plannedMeal
   */
  async function handleRemove(plannedMeal) {
    // A meal added moments ago may not have its server id back yet; removing
    // mid-flight is a rare enough race to skip rather than build a request
    // queue for.
    if (plan === null || plannedMeal.id === null) {
      return;
    }
    const previous = plan;
    const id = plannedMeal.id;
    plan = { ...plan, meals: plan.meals.filter((m) => m.id !== id) };
    renderAll();
    try {
      plan = await deleteMeal(weekStart, id);
    } catch {
      plan = previous;
      error = "Couldn't remove that meal — try again.";
    }
    renderAll();
  }

  /**
   * @param {string} query
   * @returns {Promise<RecipeSummary[]>}
   */
  async function handleSearch(query) {
    // Same match as Browse's search box, over every save, on the session index.
    const loadedIndex = await loadRecipeIndex();
    const { results } = searchLocally(
      loadedIndex,
      { ...emptyFilters(), query, segment: "all" },
      { favourites: false },
    );
    return results.slice(0, SEARCH_LIMIT);
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
    // Private mode or blocked storage: the toggle still works for this visit.
  }
}

/**
 * @param {PlannedMeal[]} meals
 * @returns {Map<string, Partial<Record<MealSlot, PlannedMeal>>>}
 */
function groupMeals(meals) {
  /** @type {Map<string, Partial<Record<MealSlot, PlannedMeal>>>} */
  const byDay = new Map();
  for (const meal of meals) {
    const forDay = byDay.get(meal.day) ?? {};
    forDay[meal.meal] = meal;
    byDay.set(meal.day, forDay);
  }
  return byDay;
}

/**
 * @param {string} text
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function navButton(text, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn plan__nav-btn";
  button.textContent = text;
  button.addEventListener("click", onClick);
  return button;
}
