// @ts-check

import { getRecipe, updateRecipe } from "../api/client.js";
import { Chip } from "../components/Chip.js";
import { extractNumber, scaleIngredient } from "../lib/scale.js";
import { hasValue } from "../lib/format.js";

/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */

/**
 * Render the recipe-detail view into container.
 * @param {HTMLElement} container
 * @param {string} code
 * @returns {Promise<void>}
 */
export async function renderDetail(container, code) {
  const recipe = await getRecipe(code);
  container.replaceChildren();

  const article = document.createElement("article");
  article.className = "detail";
  article.append(
    buildHero(recipe),
    buildScaler(recipe),
    buildColumns(recipe),
    buildTags(recipe),
    buildNotes(recipe),
  );
  container.append(article);
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildHero(recipe) {
  const hero = document.createElement("header");
  hero.className = "detail__hero";

  const src = recipe.cloudinary_url ?? recipe.thumbnail_url;
  if (src) {
    const img = document.createElement("img");
    img.className = "detail__img";
    img.src = src;
    img.alt = recipe.title;
    hero.append(img);
  }

  const title = document.createElement("h1");
  title.className = "detail__title";
  title.textContent = recipe.title;

  const meta = document.createElement("div");
  meta.className = "detail__meta";
  for (const value of [
    recipe.course,
    recipe.cuisine_type,
    recipe.difficulty,
    recipe.meal_type,
  ]) {
    if (hasValue(value)) {
      meta.append(Chip(value));
    }
  }

  hero.append(buildFavButton(recipe), title, meta);

  const times = buildTimes(recipe);
  if (times) {
    hero.append(times);
  }
  return hero;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLButtonElement}
 */
function buildFavButton(recipe) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "detail__fav";
  let favourite = recipe.is_favorite;

  const paint = () => {
    button.textContent = favourite ? "\u2605 Saved" : "\u2606 Save";
    button.setAttribute("aria-pressed", String(favourite));
    button.classList.toggle("detail__fav--active", favourite);
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
 * @returns {HTMLElement | null}
 */
function buildTimes(recipe) {
  /** @type {[string, string | null][]} */
  const entries = [
    ["Prep", recipe.prep_time],
    ["Cook", recipe.cook_time],
    ["Skill", recipe.skill_level],
  ];
  const shown = entries.filter(([, value]) => Boolean(value));
  if (shown.length === 0) {
    return null;
  }
  const dl = document.createElement("dl");
  dl.className = "detail__times";
  for (const [label, value] of shown) {
    const dt = document.createElement("dt");
    dt.textContent = label;
    const dd = document.createElement("dd");
    dd.textContent = value ?? "";
    dl.append(dt, dd);
  }
  return dl;
}

/**
 * The scaling widget: by servings, or anchored to one ingredient's amount.
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildScaler(recipe) {
  const section = document.createElement("section");
  section.className = "scaler";
  section.setAttribute("aria-label", "Scale recipe");

  const badge = document.createElement("span");
  badge.className = "scaler__factor";

  const servingsRow = buildServingsRow(recipe, applyFactor);
  const anchorRow = buildAnchorRow(recipe, applyFactor);

  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "scaler__reset";
  reset.textContent = "Reset";
  reset.addEventListener("click", () => applyFactor(1));

  section.append(servingsRow, anchorRow, reset, badge);

  /**
   * @param {number} factor
   */
  function applyFactor(factor) {
    const rounded = Math.round(factor * 10000) / 10000;
    badge.textContent = rounded === 1 ? "Original amounts" : `Scaled \u00d7${rounded}`;
    for (const li of document.querySelectorAll(".ingredient")) {
      const raw = li.getAttribute("data-raw");
      if (raw === null) {
        continue;
      }
      li.textContent = rounded === 1 ? raw : scaleIngredient(raw, rounded);
      li.classList.toggle("ingredient--scaled", rounded !== 1);
    }
  }

  applyFactor(1);
  return section;
}

/**
 * @param {RecipeDetail} recipe
 * @param {(factor: number) => void} onScale
 * @returns {HTMLElement}
 */
function buildServingsRow(recipe, onScale) {
  const row = document.createElement("div");
  row.className = "scaler__row";

  const label = document.createElement("label");
  label.className = "scaler__label";
  label.textContent = "Servings";
  const input = document.createElement("input");
  input.type = "number";
  input.min = "1";
  input.step = "1";
  input.className = "scaler__input";
  const id = "scaler-servings";
  input.id = id;
  label.htmlFor = id;

  if (recipe.base_servings === null) {
    input.disabled = true;
    input.placeholder = "n/a";
    const note = document.createElement("span");
    note.className = "scaler__note";
    note.textContent = "No base servings recorded";
    row.append(label, input, note);
    return row;
  }

  const base = recipe.base_servings;
  input.value = String(base);
  input.addEventListener("input", () => {
    const target = Number(input.value);
    if (target > 0) {
      onScale(target / base);
    }
  });
  row.append(label, input);
  return row;
}

/**
 * @param {RecipeDetail} recipe
 * @param {(factor: number) => void} onScale
 * @returns {HTMLElement}
 */
function buildAnchorRow(recipe, onScale) {
  const row = document.createElement("div");
  row.className = "scaler__row";

  const scalable = recipe.ingredients.filter((line) => extractNumber(line) !== null);
  if (scalable.length === 0) {
    return row;
  }

  const label = document.createElement("label");
  label.className = "scaler__label";
  label.textContent = "Set amount for";
  const select = document.createElement("select");
  select.className = "scaler__select";
  const id = "scaler-anchor";
  select.id = id;
  label.htmlFor = id;
  for (const line of scalable) {
    const option = document.createElement("option");
    option.value = line;
    option.textContent = line;
    select.append(option);
  }

  const amount = document.createElement("input");
  amount.type = "number";
  amount.min = "0";
  amount.step = "any";
  amount.className = "scaler__input";
  amount.setAttribute("aria-label", "Target amount");

  amount.addEventListener("input", () => {
    const base = extractNumber(select.value);
    const target = Number(amount.value);
    if (base && base > 0 && target > 0) {
      onScale(target / base);
    }
  });

  row.append(label, select, amount);
  return row;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildColumns(recipe) {
  const columns = document.createElement("div");
  columns.className = "detail__columns";
  columns.append(buildIngredients(recipe), buildInstructions(recipe));
  return columns;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildIngredients(recipe) {
  const section = document.createElement("section");
  section.className = "detail__ingredients";

  const heading = document.createElement("h2");
  heading.className = "detail__section-title";
  heading.textContent = "Ingredients";
  section.append(heading, buildCopyButton(recipe));

  const list = document.createElement("ul");
  list.className = "ingredient-list";
  for (const line of recipe.ingredients) {
    const li = document.createElement("li");
    li.className = "ingredient";
    li.setAttribute("data-raw", line);
    li.textContent = line;
    list.append(li);
  }
  section.append(list);
  return section;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLButtonElement}
 */
function buildCopyButton(recipe) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "detail__copy";
  button.textContent = "Copy list";
  button.addEventListener("click", async () => {
    await navigator.clipboard.writeText(recipe.ingredients.join("\n"));
    button.textContent = "Copied\u2713";
    window.setTimeout(() => {
      button.textContent = "Copy list";
    }, 1500);
  });
  return button;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildInstructions(recipe) {
  const section = document.createElement("section");
  section.className = "detail__instructions";

  const heading = document.createElement("h2");
  heading.className = "detail__section-title";
  heading.textContent = "Method";
  section.append(heading);

  if (recipe.instructions.length === 0) {
    const note = document.createElement("p");
    note.className = "state-msg";
    note.textContent = "No method captured for this recipe.";
    section.append(note);
    return section;
  }

  const list = document.createElement("ol");
  list.className = "instruction-list";
  for (const step of recipe.instructions) {
    const li = document.createElement("li");
    li.textContent = step;
    list.append(li);
  }
  section.append(list);
  return section;
}

/** Tag groups shown as chips at the foot of the detail page. */
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
  save.className = "notes__save";
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
