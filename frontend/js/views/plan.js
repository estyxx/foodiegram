// @ts-check

import { deleteMeal, getPlan, getRecipe, getRecipes, upsertMeal } from "../api/client.js";
import { BalancePanel } from "../components/BalancePanel.js";
import { DayColumn } from "../components/DayColumn.js";
import { formatDayLabel, formatWeekRange } from "../lib/format.js";
import { addDays, isoDate, mondayOf, weekDays } from "../lib/week.js";

/** @typedef {import("../api/client.js").PlanResponse} PlanResponse */
/** @typedef {import("../api/client.js").PlannedMeal} PlannedMeal */
/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */
/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */
/** @typedef {import("../components/DayColumn.js").MealDisplay} MealDisplay */
/** @typedef {import("../lib/week.js").MealSlot} MealSlot */

const WEEK_STEP_DAYS = 7;
const SEARCH_LIMIT = 20;

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
  /** @type {Map<string, MealDisplay>} */
  const recipesByCode = new Map();
  let error = "";

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
  nav.append(
    navButton("← Previous week", () => void changeWeek(-WEEK_STEP_DAYS)),
    navButton("This week", () => void goToWeek(mondayOf(new Date()))),
    navButton("Next week →", () => void changeWeek(WEEK_STEP_DAYS)),
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
    onRemove: handleRemove, onSearch: handleSearch };
  const columns = weekDays(weekStart).map(() => DayColumn(handlers));
  grid.append(...columns.map((column) => column.element));

  container.append(header, balancePanel.element, errorMsg, loading, grid);

  /**
   * @param {string} code
   * @returns {MealDisplay}
   */
  function pickDisplay(code) {
    const known = recipesByCode.get(code);
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
    const missing = [...new Set(meals.map((meal) => meal.recipe_code))].filter(
      (code) => !recipesByCode.has(code),
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

    range.textContent = formatWeekRange(weekStart, addDays(weekStart, 6));
    balancePanel.render(plan.balance, plan.oily_fish);

    const mealsByDay = groupMeals(plan.meals);
    weekDays(weekStart).forEach((day, index) => {
      columns[index].render({
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
      const fetched = await getPlan(weekStart);
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
        { id: null, day, meal, recipe_code: recipe.code, portions: 2 },
      ],
    };
    error = "";
    renderAll();
    try {
      plan = await upsertMeal(weekStart, { day, meal, recipe_code: recipe.code, portions: 2 });
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
    return getRecipes({ q: query }, { limit: SEARCH_LIMIT });
  }

  await goToWeek(weekStart);
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
