// @ts-check

import { updateRecipe } from "../api/client.js";
import { displayTitle } from "../lib/format.js";
import { categoryFieldset, lines, textField } from "../lib/recipeForm.js";

/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */
/** @typedef {import("../api/client.js").MedCategory} MedCategory */

const DIFFICULTIES = ["unknown", "easy", "medium", "hard"];
const LANGUAGES = /** @type {const} */ ([
  ["it", "Italiano"],
  ["en", "English"],
]);

/**
 * @typedef {object} EditRecipeDialogView
 * @property {HTMLDialogElement} element
 * @property {(recipe: RecipeDetail) => Promise<RecipeDetail | null>} open
 *   Resolves the updated recipe once saved, or null if cancelled / unchanged.
 */

/**
 * Edit a recipe in place through the widened PATCH (D42): content fields, times,
 * difficulty, Mediterranean categories, content language and the archived flag.
 * Each saved field becomes user-owned, so promote and sync push never overwrite
 * it. A native <dialog> gives focus trapping and Escape-to-close for free.
 * @returns {EditRecipeDialogView}
 */
export function EditRecipeDialog() {
  const dialog = document.createElement("dialog");
  dialog.className = "custom-recipe edit-recipe";
  dialog.setAttribute("aria-labelledby", "edit-recipe-title");

  /** @type {(updated: RecipeDetail | null) => void} */
  let settle = () => {};
  /** @type {RecipeDetail | null} */
  let result = null;
  dialog.addEventListener("close", () => settle(result));

  return {
    element: dialog,
    open(recipe) {
      result = null;
      dialog.replaceChildren(
        buildForm(
          recipe,
          (updated) => {
            result = updated;
            dialog.close();
          },
          () => dialog.close(),
        ),
      );
      dialog.showModal();
      const first = dialog.querySelector("input, textarea");
      if (first instanceof HTMLElement) {
        first.focus();
      }
      return new Promise((resolve) => {
        settle = resolve;
      });
    },
  };
}

/**
 * @param {RecipeDetail} recipe
 * @param {(updated: RecipeDetail) => void} onDone
 * @param {() => void} onCancel
 * @returns {HTMLFormElement}
 */
function buildForm(recipe, onDone, onCancel) {
  const edited = new Set(recipe.edited_fields);
  const form = document.createElement("form");
  form.className = "custom-recipe__form";
  form.noValidate = true;

  const heading = document.createElement("h2");
  heading.className = "custom-recipe__title";
  heading.id = "edit-recipe-title";
  heading.textContent = `Edit “${displayTitle(recipe)}”`;

  const title = textField("Title", "input", recipe.title ?? "");
  const summary = textField("Summary", "textarea", recipe.summary ?? "");
  const ingredients = textField(
    "Ingredients (one per line)",
    "textarea",
    recipe.ingredients.join("\n"),
  );
  const method = textField(
    "Method (one step per line)",
    "textarea",
    recipe.instructions.join("\n"),
  );
  const prep = textField("Prep time", "input", recipe.prep_time ?? "");
  const cook = textField("Cook time", "input", recipe.cook_time ?? "");
  const total = textField("Total time", "input", recipe.total_time ?? "");
  const difficulty = selectField("Difficulty", DIFFICULTIES, recipe.difficulty);
  const language = selectField(
    "Content language",
    LANGUAGES.map(([code]) => code),
    recipe.language,
    (code) => LANGUAGES.find(([value]) => value === code)?.[1] ?? code,
  );
  const categories = categoryFieldset(recipe.mediterranean_categories);
  const archived = checkboxField("Archived (hidden from Browse)", recipe.archived);

  const error = document.createElement("p");
  error.className = "state-msg state-msg--error custom-recipe__error";
  error.setAttribute("role", "alert");
  error.hidden = true;

  const save = document.createElement("button");
  save.type = "submit";
  save.className = "btn btn--primary";
  save.textContent = "Save";

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "btn-ghost";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", onCancel);

  const actions = document.createElement("div");
  actions.className = "custom-recipe__actions";
  actions.append(save, cancel);

  form.append(
    heading,
    mark("title", title.element, edited),
    mark("summary", summary.element, edited),
    mark("ingredients", ingredients.element, edited),
    mark("instructions", method.element, edited),
    mark("prep_time", prep.element, edited),
    mark("cook_time", cook.element, edited),
    mark("total_time", total.element, edited),
    mark("difficulty", difficulty.element, edited),
    mark("language", language.element, edited),
    mark("mediterranean_categories", categories.element, edited),
    archived.element,
    error,
    actions,
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const patch = changedFields(recipe, {
      title: title.control.value.trim(),
      summary: summary.control.value.trim(),
      ingredients: lines(ingredients.control.value),
      instructions: lines(method.control.value),
      prep_time: prep.control.value.trim(),
      cook_time: cook.control.value.trim(),
      total_time: total.control.value.trim(),
      difficulty: difficulty.control.value,
      language: language.control.value,
      mediterranean_categories: categories.read(),
      archived: archived.control.checked,
    });
    if (Object.keys(patch).length === 0) {
      onDone(recipe);
      return;
    }
    save.disabled = true;
    save.textContent = "Saving…";
    try {
      onDone(await updateRecipe(recipe.code, patch));
    } catch {
      error.hidden = false;
      error.textContent = "Couldn’t save it — try again.";
      save.disabled = false;
      save.textContent = "Save";
    }
  });
  return form;
}

/**
 * Keep only the fields whose value differs from the current recipe, so a save
 * records exactly what the user changed (and nothing else becomes user-owned).
 * @param {RecipeDetail} recipe
 * @param {Record<string, unknown>} next
 * @returns {Record<string, unknown>}
 */
function changedFields(recipe, next) {
  /** @type {Record<string, unknown>} */
  const patch = {};
  for (const [key, value] of Object.entries(next)) {
    if (key === "mediterranean_categories") {
      if (!sameCategories(/** @type {MedCategory[]} */ (value), recipe[key])) {
        patch[key] = value;
      }
      continue;
    }
    // A missing optional string reads back as null; an empty input is "". Treat
    // them as equal so clearing-an-already-empty field is not a change.
    const previous = /** @type {any} */ (recipe)[key] ?? "";
    if (JSON.stringify(value) !== JSON.stringify(previous)) {
      patch[key] = value;
    }
  }
  return patch;
}

/**
 * Compare category lists by what the user can set (category, servings, oily),
 * ignoring order and the stored `source` field.
 * @param {MedCategory[]} a
 * @param {MedCategory[]} b
 * @returns {boolean}
 */
function sameCategories(a, b) {
  const norm = (/** @type {MedCategory[]} */ list) =>
    list
      .map((c) => ({
        category: c.category,
        servings: c.servings,
        is_oily_fish: c.is_oily_fish ?? false,
      }))
      .sort((x, y) => x.category.localeCompare(y.category));
  return JSON.stringify(norm(a)) === JSON.stringify(norm(b));
}

/**
 * Append an "edited" marker to a field's label when it is user-owned.
 * @param {string} field
 * @param {HTMLElement} element
 * @param {Set<string>} edited
 * @returns {HTMLElement}
 */
function mark(field, element, edited) {
  if (edited.has(field)) {
    const label = element.querySelector(".custom-recipe__label");
    if (label) {
      const badge = document.createElement("span");
      badge.className = "edit-recipe__marker";
      badge.textContent = " · edited";
      badge.title = "You edited this; extraction won't overwrite it.";
      label.append(badge);
    }
  }
  return element;
}

/**
 * A labelled <select>.
 * @param {string} label
 * @param {readonly string[]} values
 * @param {string} current
 * @param {(value: string) => string} [labelFor]
 * @returns {{ element: HTMLLabelElement, control: HTMLSelectElement }}
 */
function selectField(label, values, current, labelFor) {
  const wrap = document.createElement("label");
  wrap.className = "custom-recipe__field";
  const text = document.createElement("span");
  text.className = "custom-recipe__label";
  text.textContent = label;
  const control = document.createElement("select");
  control.className = "custom-recipe__control";
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labelFor ? labelFor(value) : value;
    option.selected = value === current;
    control.append(option);
  }
  wrap.append(text, control);
  return { element: wrap, control };
}

/**
 * A labelled checkbox (label text after the box).
 * @param {string} label
 * @param {boolean} checked
 * @returns {{ element: HTMLLabelElement, control: HTMLInputElement }}
 */
function checkboxField(label, checked) {
  const wrap = document.createElement("label");
  wrap.className = "custom-recipe__field custom-recipe__field--check";
  const control = document.createElement("input");
  control.type = "checkbox";
  control.checked = checked;
  const text = document.createElement("span");
  text.className = "custom-recipe__label";
  text.textContent = label;
  wrap.append(control, text);
  return { element: wrap, control };
}
