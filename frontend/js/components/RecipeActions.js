// @ts-check

import { addMeal } from "../api/client.js";
import { setFavourite } from "../lib/recipeIndex.js";
import { DEFAULT_PORTIONS, mondayOf, weekDays } from "../lib/week.js";

/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */
/** @typedef {import("../lib/week.js").MealSlot} MealSlot */

/**
 * @typedef {object} MenuItem
 * @property {string} glyph
 * @property {string} label
 * @property {() => void} onSelect
 */
/**
 * @typedef {object} RecipeActionsProps
 * @property {RecipeDetail} recipe
 * @property {(() => void) | null} onStartCooking null when there are no steps
 * @property {() => string} recipeText the scaled recipe as plain text
 * @property {() => MenuItem[]} menuItems read on each open, so labels stay current
 * @property {(message: string) => void} onAnnounce
 */

const COPIED_MS = 1900;
const DAY_CODES = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/**
 * Start cooking, then Save · Plan · Copy · Export · ⋯, with the day picker
 * that Plan opens below the row.
 * @param {RecipeActionsProps} props
 * @returns {HTMLElement}
 */
export function RecipeActions({ recipe, onStartCooking, recipeText, menuItems, onAnnounce }) {
  const wrap = document.createElement("div");
  wrap.className = "rd-actions";

  const row = document.createElement("div");
  row.className = "rd-actions__row";

  if (onStartCooking !== null) {
    const cook = document.createElement("button");
    cook.type = "button";
    cook.className = "rd-actions__cook";
    const play = document.createElement("span");
    play.setAttribute("aria-hidden", "true");
    play.textContent = "▶";
    cook.append(play, document.createTextNode("Start cooking"));
    cook.addEventListener("click", onStartCooking);
    row.append(cook);
  }

  const group = document.createElement("div");
  group.className = "rd-actions__group";

  let favourite = recipe.is_favorite;
  const save = actionButton(() => toggleSave());
  const paintSave = () => {
    paint(save, favourite ? "♥" : "♡", favourite ? "Saved" : "Save", favourite);
    save.setAttribute("aria-pressed", String(favourite));
  };
  paintSave();

  const plan = actionButton(() => setPicker(picker.hidden === true));
  plan.setAttribute("aria-expanded", "false");
  paint(plan, "＋", "Plan", false);

  const copy = actionButton(() => copyRecipe());
  paint(copy, "⧉", "Copy", false);

  const exportButton = actionButton(() => exportRecipe());
  paint(exportButton, "↓", "Export", false);

  const more = document.createElement("div");
  more.className = "rd-actions__more";
  const moreButton = document.createElement("button");
  moreButton.type = "button";
  moreButton.className = "rd-actions__btn rd-actions__btn--more";
  moreButton.textContent = "⋯";
  moreButton.setAttribute("aria-label", "More actions");
  moreButton.setAttribute("aria-haspopup", "menu");
  moreButton.setAttribute("aria-expanded", "false");
  const menu = document.createElement("div");
  menu.className = "rd-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "More actions");
  menu.hidden = true;
  moreButton.addEventListener("click", () => setMenu(menu.hidden === true));
  menu.addEventListener("keydown", onMenuKey);
  more.append(moreButton, menu);

  group.append(save, plan, copy, exportButton, more);
  row.append(group);

  const picker = buildDayPicker();
  picker.hidden = true;
  wrap.append(row, picker);
  return wrap;

  async function toggleSave() {
    save.disabled = true;
    try {
      // Through the index, so Browse shows the new flag without refetching.
      favourite = await setFavourite(recipe.code, !favourite);
      paintSave();
      onAnnounce(favourite ? "Saved to favourites" : "Removed from favourites");
    } catch {
      onAnnounce("Couldn't update favourites — try again.");
    } finally {
      save.disabled = false;
    }
  }

  async function copyRecipe() {
    try {
      await navigator.clipboard.writeText(recipeText());
    } catch {
      onAnnounce("Couldn't copy — your browser blocked the clipboard.");
      return;
    }
    paint(copy, "✓", "Copied", true);
    onAnnounce("Recipe copied as text");
    window.setTimeout(() => paint(copy, "⧉", "Copy", false), COPIED_MS);
  }

  function exportRecipe() {
    const blob = new Blob([recipeText()], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${recipe.code}.txt`;
    link.click();
    URL.revokeObjectURL(url);
    onAnnounce("Exported as a text file");
  }

  /**
   * @returns {HTMLElement}
   */
  function buildDayPicker() {
    const grid = document.createElement("div");
    grid.className = "rd-days";
    grid.setAttribute("role", "group");
    grid.setAttribute("aria-label", "Add to a day this week");
    const meal = mealFor(recipe);
    weekDays(mondayOf(new Date())).forEach((day, index) => {
      const date = Number(day.slice(8));
      const button = document.createElement("button");
      button.type = "button";
      button.className = "rd-days__day";
      button.textContent = `${DAY_CODES[index]} ${date}`;
      button.setAttribute("aria-label", `Add to ${DAY_NAMES[index]} ${date}, ${meal}`);
      button.addEventListener("click", async () => {
        setPicker(false);
        try {
          await addMeal(mondayOf(new Date()), {
            day,
            meal,
            recipe_code: recipe.code,
            portions: DEFAULT_PORTIONS,
          });
          onAnnounce(`Added to ${DAY_NAMES[index]} ${date} · ${meal}`);
        } catch {
          onAnnounce("Couldn't add it to the plan — try again.");
        }
      });
      grid.append(button);
    });
    return grid;
  }

  /**
   * @param {boolean} open
   */
  function setPicker(open) {
    picker.hidden = !open;
    plan.setAttribute("aria-expanded", String(open));
    paint(plan, "＋", "Plan", open);
    if (open) {
      setMenu(false);
    }
  }

  /**
   * @param {boolean} open
   */
  function setMenu(open) {
    if (open === (menu.hidden !== true)) {
      return;
    }
    menu.hidden = !open;
    moreButton.setAttribute("aria-expanded", String(open));
    if (!open) {
      document.removeEventListener("pointerdown", onOutside, true);
      document.removeEventListener("keydown", onEscape, true);
      return;
    }
    setPicker(false);
    menu.replaceChildren(
      ...menuItems().map((item) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "rd-menu__item";
        button.setAttribute("role", "menuitem");
        const glyph = document.createElement("span");
        glyph.className = "rd-menu__glyph";
        glyph.setAttribute("aria-hidden", "true");
        glyph.textContent = item.glyph;
        button.append(glyph, document.createTextNode(item.label));
        button.addEventListener("click", () => {
          setMenu(false);
          item.onSelect();
        });
        return button;
      }),
    );
    document.addEventListener("pointerdown", onOutside, true);
    document.addEventListener("keydown", onEscape, true);
    menuButtons()[0]?.focus();
  }

  /**
   * @param {PointerEvent} event
   */
  function onOutside(event) {
    if (!more.isConnected || !more.contains(/** @type {Node} */ (event.target))) {
      setMenu(false);
    }
  }

  /**
   * @param {KeyboardEvent} event
   */
  function onEscape(event) {
    if (event.key === "Escape") {
      setMenu(false);
      moreButton.focus();
    }
  }

  /**
   * Up/Down/Home/End move between items, as a menu's keyboard model expects.
   * @param {KeyboardEvent} event
   */
  function onMenuKey(event) {
    const items = menuButtons();
    const at = items.indexOf(/** @type {HTMLButtonElement} */ (document.activeElement));
    /** @type {Record<string, number>} */
    const moves = {
      ArrowDown: (at + 1) % items.length,
      ArrowUp: (at - 1 + items.length) % items.length,
      Home: 0,
      End: items.length - 1,
    };
    if (event.key in moves) {
      event.preventDefault();
      items[moves[event.key]]?.focus();
    }
  }

  /** @returns {HTMLButtonElement[]} */
  function menuButtons() {
    return [...menu.querySelectorAll("button")];
  }
}

/**
 * Lunch-type recipes go to lunch; everything else to dinner, the slot most
 * saves are cooked for.
 * @param {RecipeDetail} recipe
 * @returns {MealSlot}
 */
function mealFor(recipe) {
  return recipe.meal_type === "lunch" ? "lunch" : "dinner";
}

/**
 * @param {() => void} onClick
 * @returns {HTMLButtonElement}
 */
function actionButton(onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "rd-actions__btn";
  button.addEventListener("click", onClick);
  return button;
}

/**
 * Glyph + label; the label hides on a phone, so it is also the aria-label.
 * @param {HTMLButtonElement} button
 * @param {string} glyph
 * @param {string} label
 * @param {boolean} on painted in the pressed style
 */
function paint(button, glyph, label, on) {
  const icon = document.createElement("span");
  icon.className = "rd-actions__glyph";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = glyph;
  const text = document.createElement("span");
  text.className = "rd-actions__label";
  text.textContent = label;
  button.replaceChildren(icon, text);
  button.setAttribute("aria-label", label);
  button.title = label;
  button.classList.toggle("rd-actions__btn--on", on);
}
