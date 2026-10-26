// @ts-check

import { CATEGORY } from "../lib/categories.js";
import { displayTitle } from "../lib/format.js";

/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */
/** @typedef {import("../api/client.js").RecipeDraft} RecipeDraft */
/** @typedef {import("../api/client.js").MedCategory} MedCategory */

const SERVINGS_STEP = "0.25";
const DEFAULT_SERVINGS = "1";

/**
 * @typedef {object} CustomRecipeRequest
 * @property {RecipeDetail | null} base The recipe this is a version of, or null.
 * @property {string} slotLabel Where it will go, e.g. "mar 27 ott · Lunch".
 * @property {(draft: RecipeDraft) => Promise<void>} onSave Saves and slots it.
 */

/**
 * @typedef {object} CustomRecipeDialogView
 * @property {HTMLDialogElement} element
 * @property {(request: CustomRecipeRequest) => Promise<boolean>} open
 *   Resolves true once saved, false if cancelled.
 */

/**
 * "My version of…" (D23 from the web): a modal form prefilled from the base
 * recipe, whose Mediterranean categories the user sets by hand. A native
 * <dialog> gives focus trapping and Escape-to-close for free.
 * @returns {CustomRecipeDialogView}
 */
export function CustomRecipeDialog() {
  const dialog = document.createElement("dialog");
  dialog.className = "custom-recipe";
  dialog.setAttribute("aria-labelledby", "custom-recipe-title");

  /** @type {(saved: boolean) => void} */
  let settle = () => {};
  let saved = false;
  dialog.addEventListener("close", () => settle(saved));

  return {
    element: dialog,
    open(request) {
      saved = false;
      dialog.replaceChildren(
        buildForm(request, () => {
          saved = true;
          dialog.close();
        }, () => dialog.close()),
      );
      dialog.showModal();
      const first = dialog.querySelector("input");
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
 * @param {CustomRecipeRequest} request
 * @param {() => void} onDone
 * @param {() => void} onCancel
 * @returns {HTMLFormElement}
 */
function buildForm(request, onDone, onCancel) {
  const { base } = request;
  const form = document.createElement("form");
  form.className = "custom-recipe__form";
  form.noValidate = true;

  const heading = document.createElement("h2");
  heading.className = "custom-recipe__title";
  heading.id = "custom-recipe-title";
  heading.textContent = base ? `My version of “${displayTitle(base)}”` : "Write my own";

  const where = document.createElement("p");
  where.className = "custom-recipe__where";
  where.textContent = `Saved to your library, then added to ${request.slotLabel}.`;

  const title = textField("Title", "input", base?.title ?? "");
  const ingredients = textField(
    "Ingredients (one per line)",
    "textarea",
    (base?.ingredients ?? []).join("\n"),
  );
  const method = textField(
    "Method (one step per line, optional)",
    "textarea",
    (base?.instructions ?? []).join("\n"),
  );
  const categories = categoryFieldset(base?.mediterranean_categories ?? []);

  const error = document.createElement("p");
  error.className = "state-msg state-msg--error custom-recipe__error";
  error.setAttribute("role", "alert");
  error.hidden = true;

  const save = document.createElement("button");
  save.type = "submit";
  save.className = "btn btn--primary";
  save.textContent = "Save & add";

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
    where,
    title.element,
    ingredients.element,
    method.element,
    categories.element,
    error,
    actions,
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const draft = {
      title: title.control.value.trim(),
      ingredients: lines(ingredients.control.value),
      instructions: lines(method.control.value),
      mediterranean_categories: categories.read(),
      inspired_by: base ? [base.code] : [],
    };
    const problem =
      draft.title === ""
        ? "Give it a title."
        : draft.ingredients.length === 0
          ? "Add at least one ingredient."
          : "";
    error.hidden = problem === "";
    error.textContent = problem;
    if (problem !== "") {
      return;
    }
    save.disabled = true;
    save.textContent = "Saving…";
    try {
      await request.onSave(draft);
      onDone();
    } catch {
      error.hidden = false;
      error.textContent = "Couldn’t save it — try again.";
      save.disabled = false;
      save.textContent = "Save & add";
    }
  });
  return form;
}

/**
 * @param {string} text
 * @returns {string[]}
 */
function lines(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "");
}

/**
 * A labelled single-line or multi-line text control.
 * @template {"input" | "textarea"} K
 * @param {string} label
 * @param {K} tag
 * @param {string} value
 * @returns {{ element: HTMLLabelElement, control: HTMLElementTagNameMap[K] }}
 */
function textField(label, tag, value) {
  const wrap = document.createElement("label");
  wrap.className = "custom-recipe__field";
  const text = document.createElement("span");
  text.className = "custom-recipe__label";
  text.textContent = label;
  const control = document.createElement(tag);
  control.className = "custom-recipe__control";
  control.value = value;
  if (control instanceof HTMLTextAreaElement) {
    control.rows = 5;
  }
  wrap.append(text, control);
  return { element: wrap, control };
}

/**
 * One checkbox + servings per Mediterranean category, prefilled from the base
 * recipe. These are what the weekly balance counts, so the user sets them by
 * hand; nothing is inferred.
 * @param {MedCategory[]} current
 * @returns {{ element: HTMLFieldSetElement, read: () => MedCategory[] }}
 */
function categoryFieldset(current) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "custom-recipe__categories";
  const legend = document.createElement("legend");
  legend.className = "custom-recipe__label";
  legend.textContent = "Counts toward (servings per portion)";
  fieldset.append(legend);

  const byCategory = new Map(current.map((serving) => [serving.category, serving]));
  /** @type {(() => MedCategory | null)[]} */
  const readers = [];

  for (const [key, tokens] of Object.entries(CATEGORY)) {
    const existing = byCategory.get(key);
    const row = document.createElement("div");
    row.className = "custom-recipe__category";

    const checkLabel = document.createElement("label");
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = existing !== undefined;
    checkLabel.append(check, document.createTextNode(` ${tokens.label}`));

    const servings = document.createElement("input");
    servings.type = "number";
    servings.className = "custom-recipe__servings";
    servings.min = SERVINGS_STEP;
    servings.step = SERVINGS_STEP;
    servings.value = existing ? String(existing.servings) : DEFAULT_SERVINGS;
    servings.disabled = !check.checked;
    servings.setAttribute("aria-label", `${tokens.label} servings`);
    check.addEventListener("change", () => {
      servings.disabled = !check.checked;
    });
    row.append(checkLabel, servings);

    /** @type {HTMLInputElement | null} */
    let oily = null;
    if (key === "fish") {
      const oilyLabel = document.createElement("label");
      const oilyCheck = document.createElement("input");
      oilyCheck.type = "checkbox";
      oilyCheck.checked = existing?.is_oily_fish ?? false;
      oilyLabel.append(oilyCheck, document.createTextNode(" oily"));
      row.append(oilyLabel);
      oily = oilyCheck;
    }

    fieldset.append(row);
    readers.push(() => {
      const amount = Number(servings.value);
      if (!check.checked || !(amount > 0)) {
        return null;
      }
      return { category: key, servings: amount, is_oily_fish: oily?.checked ?? false };
    });
  }

  return {
    element: fieldset,
    read: () => readers.map((reader) => reader()).filter((serving) => serving !== null),
  };
}
