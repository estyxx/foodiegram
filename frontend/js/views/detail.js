// @ts-check

import { getRecipe, updateRecipe } from "../api/client.js";
import { Chip } from "../components/Chip.js";
import { formatQuantity, hasValue, humanise } from "../lib/format.js";

/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */

const NUMBER_RE = /(\d+\.?\d*)/;

/**
 * Render the recipe-detail view (Dispensa v3 magazine layout) into container.
 *
 * Layout mirrors Dispensa v3: method on the left, a sticky ingredients +
 * scaling panel on the right.
 * @param {HTMLElement} container
 * @param {string} code
 * @returns {Promise<void>}
 */
export async function renderDetail(container, code) {
  const recipe = await getRecipe(code);
  container.replaceChildren();

  const back = document.createElement("a");
  back.className = "detail__back";
  back.href = "#browse";
  back.textContent = "\u2190 Back to browse";

  const left = document.createElement("div");
  left.className = "detail__left";
  left.append(buildHead(recipe), buildMethod(recipe));

  const grid = document.createElement("div");
  grid.className = "detail__grid";
  grid.append(left, buildIngredients(recipe));

  container.append(back, grid, buildTags(recipe), buildNotes(recipe));
}

/* ---- Left column: head + method ---------------------------------------- */

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildHead(recipe) {
  const head = document.createElement("header");
  head.className = "detail__head";

  const photo = buildPhoto(recipe);
  if (photo) {
    head.append(photo);
  }

  const eyebrowText = [recipe.cuisine_type, recipe.course]
    .filter(hasValue)
    .map(humanise)
    .join(" \u00b7 ");
  if (eyebrowText) {
    const eyebrow = document.createElement("div");
    eyebrow.className = "detail__eyebrow";
    eyebrow.textContent = eyebrowText;
    head.append(eyebrow);
  }

  head.append(buildTitle(recipe.title), buildMeta(recipe), buildSourceLink(recipe));

  const fit = buildFit(recipe);
  if (fit) {
    head.append(fit);
  }
  return head;
}

/**
 * The lead photo (Cloudinary preferred, Instagram thumbnail as fallback).
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement | null}
 */
function buildPhoto(recipe) {
  const src = recipe.cloudinary_url ?? recipe.thumbnail_url;
  if (!src) {
    return null;
  }
  const figure = document.createElement("figure");
  figure.className = "detail__photo";
  const img = document.createElement("img");
  img.className = "detail__photo-img";
  img.src = src;
  img.alt = recipe.title;
  img.loading = "lazy";
  figure.append(img);
  return figure;
}

/**
 * A link back to the original Instagram post, built from the canonical shortcode.
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildSourceLink(recipe) {
  const link = document.createElement("a");
  link.className = "detail__source";
  link.href = `https://www.instagram.com/p/${encodeURIComponent(recipe.code)}/`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "View original on Instagram \u2197";
  return link;
}

/**
 * Split a title so the last phrase can be italicised (Italian "all'" aware).
 * @param {string} title
 * @returns {HTMLElement}
 */
function buildTitle(title) {
  const h1 = document.createElement("h1");
  h1.className = "detail__title";

  const idx = title.indexOf("all'");
  let pre = "";
  let em = title;
  if (idx > 0) {
    pre = title.slice(0, idx);
    em = title.slice(idx);
  } else {
    const words = title.split(" ");
    if (words.length > 1) {
      pre = `${words.slice(0, -1).join(" ")} `;
      em = words[words.length - 1];
    }
  }
  if (pre) {
    h1.append(document.createTextNode(pre));
  }
  const emphasis = document.createElement("em");
  emphasis.textContent = em;
  h1.append(emphasis);
  return h1;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildMeta(recipe) {
  const meta = document.createElement("div");
  meta.className = "detail__meta";

  /** @type {string[]} */
  const parts = [];
  const time = [recipe.prep_time, recipe.cook_time].filter(Boolean).join(" + ");
  if (time) {
    parts.push(`\u23f1 ${time}`);
  }
  if (recipe.base_servings !== null) {
    parts.push(`serves ${recipe.base_servings}`);
  }
  if (hasValue(recipe.difficulty)) {
    parts.push(humanise(recipe.difficulty));
  }
  if (hasValue(recipe.meal_type)) {
    parts.push(humanise(recipe.meal_type));
  }

  parts.forEach((part, index) => {
    if (index > 0) {
      const sep = document.createElement("span");
      sep.setAttribute("aria-hidden", "true");
      sep.textContent = "\u00b7";
      meta.append(sep);
    }
    const span = document.createElement("span");
    span.textContent = part;
    meta.append(span);
  });
  return meta;
}

/**
 * The "Mediterranean fit" callout, shown only when v2 categories are present.
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement | null}
 */
function buildFit(recipe) {
  const cats = recipe.mediterranean_categories;
  if (cats.length === 0) {
    return null;
  }
  const labels = [...new Set(cats.map((c) => humanise(c.category)))];
  const oily = cats.some((c) => c.is_oily_fish);

  const box = document.createElement("div");
  box.className = "detail__fit";

  const swatch = document.createElement("span");
  swatch.className = "detail__fit__swatch";
  swatch.setAttribute("aria-hidden", "true");

  const body = document.createElement("div");
  const label = document.createElement("div");
  label.className = "detail__fit__label";
  label.textContent = "Mediterranean fit";
  const text = document.createElement("div");
  text.className = "detail__fit__text";
  text.textContent = `Counts toward ${labels.join(" & ")}.${
    oily ? " An oily fish — exactly what the week wants." : ""
  }`;
  body.append(label, text);

  box.append(swatch, body);
  return box;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildMethod(recipe) {
  const section = document.createElement("section");
  section.className = "detail__method";
  section.setAttribute("aria-label", "Method");

  const heading = document.createElement("h2");
  heading.className = "detail__section-title";
  heading.textContent = "Method";
  section.append(heading);

  if (recipe.instructions.length === 0) {
    const note = document.createElement("p");
    note.className = "scale-hint";
    note.textContent = "No method captured for this recipe.";
    section.append(note);
    return section;
  }

  const list = document.createElement("ol");
  list.className = "method__list";
  recipe.instructions.forEach((step, index) => {
    const item = document.createElement("li");
    item.className = "method__item";
    const num = document.createElement("span");
    num.className = "method__num";
    num.setAttribute("aria-hidden", "true");
    num.textContent = String(index + 1);
    const text = document.createElement("p");
    text.className = "method__text";
    text.textContent = step;
    item.append(num, text);
    list.append(item);
  });
  section.append(list);
  return section;
}

/* ---- Right column: ingredients + scaling ------------------------------- */

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildIngredients(recipe) {
  const panel = document.createElement("section");
  panel.className = "panel detail__panel";
  panel.setAttribute("aria-label", "Ingredients and scaling");

  const base = recipe.base_servings;
  let ratio = 1;
  /** @type {(() => void)[]} */
  const updaters = [];

  // --- servings stepper ---
  const stepper = document.createElement("div");
  stepper.className = "stepper";
  const stepLabel = document.createElement("span");
  stepLabel.className = "stepper__label";
  stepLabel.textContent = "Servings";
  const stepBtns = document.createElement("div");
  stepBtns.className = "stepper__btns";
  const dec = stepButton("\u2212", "Fewer servings", () => step(-1));
  const value = document.createElement("span");
  value.className = "stepper__val";
  value.setAttribute("aria-live", "polite");
  const inc = stepButton("+", "More servings", () => step(1));
  stepBtns.append(dec, value, inc);
  stepper.append(stepLabel, stepBtns);

  const scaleHint = document.createElement("p");
  scaleHint.className = "scale-hint";

  // --- ingredients heading + reset ---
  const head = document.createElement("div");
  head.className = "ingredients__head";
  const title = document.createElement("h2");
  title.className = "detail__section-title";
  title.textContent = "Ingredients";
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "ingredients__reset";
  reset.textContent = base === null ? "reset" : `reset to ${base}`;
  reset.hidden = true;
  reset.addEventListener("click", () => setRatio(1));
  head.append(title, reset);

  const typeHint = document.createElement("p");
  typeHint.className = "scale-hint";
  typeHint.textContent =
    "Type the amount you actually have — everything else rescales.";

  const list = document.createElement("ul");
  list.className = "ing-list";
  for (const line of recipe.ingredients) {
    list.append(buildRow(line));
  }

  if (base === null) {
    stepper.hidden = true;
  }
  panel.append(stepper, scaleHint, head, typeHint, list, buildActions(recipe));

  /**
   * @param {number} delta
   */
  function step(delta) {
    if (base === null) {
      return;
    }
    const current = Math.round(base * ratio);
    setRatio(Math.max(1, current + delta) / base);
  }

  /**
   * @param {number} next
   */
  function setRatio(next) {
    ratio = next;
    for (const update of updaters) {
      update();
    }
    const scaled = Math.abs(ratio - 1) >= 0.001;
    if (base !== null) {
      value.textContent = formatQuantity(base * ratio);
      scaleHint.textContent = scaled
        ? `Rescaled from ${base} servings`
        : `Original recipe \u00b7 serves ${base}`;
    } else {
      scaleHint.textContent = scaled ? "Rescaled to your amount" : "Original amounts";
    }
    reset.hidden = !scaled;
  }

  /**
   * @param {string} line
   * @returns {HTMLLIElement}
   */
  function buildRow(line) {
    const row = document.createElement("li");
    row.className = "ing-row";
    const match = NUMBER_RE.exec(line);
    const name = document.createElement("span");
    name.className = "ing-name";

    if (match === null) {
      const qty = document.createElement("span");
      qty.className = "ing-qty ing-qty--empty";
      qty.textContent = "\u2014";
      name.textContent = line;
      row.append(qty, name);
      return row;
    }

    const baseNum = parseFloat(match[1]);
    name.textContent = (
      line.slice(0, match.index) + line.slice(match.index + match[1].length)
    ).trim();

    const input = document.createElement("input");
    input.type = "text";
    input.inputMode = "decimal";
    input.className = "ing-qty-input";
    input.value = formatQuantity(baseNum * ratio);
    input.setAttribute("aria-label", `Amount of ${name.textContent}`);
    input.addEventListener("input", () => {
      const typed = parseFloat(input.value);
      if (Number.isFinite(typed) && typed > 0) {
        setRatio(typed / baseNum);
      }
    });
    updaters.push(() => {
      if (document.activeElement !== input) {
        input.value = formatQuantity(baseNum * ratio);
      }
    });
    row.append(input, name);
    return row;
  }

  setRatio(1);
  return panel;
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
  button.className = "stepper__btn";
  button.textContent = glyph;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", onClick);
  return button;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildActions(recipe) {
  const wrap = document.createElement("div");
  wrap.className = "panel__actions";
  wrap.append(buildSaveButton(recipe), buildCopyButton(recipe));
  return wrap;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLButtonElement}
 */
function buildSaveButton(recipe) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn";
  let favourite = recipe.is_favorite;

  const paint = () => {
    button.textContent = favourite ? "\u2605 Saved" : "\u2606 Save";
    button.setAttribute("aria-pressed", String(favourite));
    button.classList.toggle("btn--saved", favourite);
  };
  paint();

  button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const updated = await updateRecipe(recipe.code, { is_favorite: !favourite });
      favourite = updated.is_favorite;
      paint();
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLButtonElement}
 */
function buildCopyButton(recipe) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "btn";
  button.textContent = "Copy list";
  button.addEventListener("click", async () => {
    await navigator.clipboard.writeText(recipe.ingredients.join("\n"));
    button.textContent = "Copied \u2713";
    window.setTimeout(() => {
      button.textContent = "Copy list";
    }, 1500);
  });
  return button;
}

/* ---- Tag groups --------------------------------------------------------- */

const TAG_GROUPS = /** @type {const} */ ([
  ["Proteins", "proteins"],
  ["Vegetables", "vegetables"],
  ["Grains & starches", "grains_starches"],
  ["Herbs & spices", "herbs_spices"],
  ["Dietary", "dietary_tags"],
  ["Health", "health_tags"],
  ["Cooking methods", "cooking_methods"],
  ["Equipment", "equipment"],
]);

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildTags(recipe) {
  const section = document.createElement("section");
  section.className = "detail__tags";

  for (const [label, key] of TAG_GROUPS) {
    const values = recipe[key];
    if (values.length === 0) {
      continue;
    }
    const group = document.createElement("div");
    group.className = "tag-group";
    const title = document.createElement("span");
    title.className = "tag-group__label";
    title.textContent = label;
    group.append(title);
    for (const value of values) {
      group.append(Chip(value));
    }
    section.append(group);
  }
  return section;
}

/* ---- Notes -------------------------------------------------------------- */

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildNotes(recipe) {
  const section = document.createElement("section");
  section.className = "detail__notes";

  const heading = document.createElement("h2");
  heading.className = "detail__section-title";
  heading.textContent = "Your notes";

  const textarea = document.createElement("textarea");
  textarea.className = "notes__input";
  textarea.rows = 4;
  textarea.value = recipe.user_notes ?? "";
  textarea.setAttribute("aria-label", "Your notes");

  const save = document.createElement("button");
  save.type = "button";
  save.className = "btn notes__save";
  save.textContent = "Save notes";

  const status = document.createElement("span");
  status.className = "notes__status";
  status.setAttribute("aria-live", "polite");

  save.addEventListener("click", async () => {
    save.disabled = true;
    try {
      await updateRecipe(recipe.code, { user_notes: textarea.value });
      status.textContent = "Saved";
    } catch {
      status.textContent = "Could not save";
    } finally {
      save.disabled = false;
    }
  });

  section.append(heading, textarea, save, status);
  return section;
}
