// @ts-check

import { getRecipe, updateRecipe } from "../api/client.js";
import { indexedRecipe, peekRecipeIndex } from "../lib/recipeIndex.js";
import { startCooking } from "../lib/cookingSession.js";
import { parseStep } from "../lib/cookingSteps.js";
import { layoutIngredients, rowText, splitTitle } from "../lib/recipeDisplay.js";
import { capitalise, displayTitle, formatQuantity, hasValue, humanise } from "../lib/format.js";
import { CategoryChip } from "../components/CategoryChip.js";
import { IngredientsCard } from "../components/IngredientsCard.js";
import { RecipeActions } from "../components/RecipeActions.js";

/** @typedef {import("../api/client.js").RecipeDetail} RecipeDetail */
/** @typedef {import("../lib/recipeDisplay.js").IngredientLayout} IngredientLayout */
/**
 * What the header needs; the session index already has it.
 * @typedef {Pick<RecipeDetail, "title" | "author_username" | "cloudinary_url" | "thumbnail_url">} CoverFields
 */

const STATUS_MS = 2400;
const NOTES_DEBOUNCE_MS = 600;

/** The diet chips worth a place on the page; vegan says vegetarian already. */
const DIET_CHIPS = /** @type {const} */ ([
  ["vegan", "Vegan"],
  ["vegetarian", "Vegetarian"],
  ["gluten_free", "Gluten free"],
]);
const MAX_DIET_CHIPS = 2;

/**
 * Render the recipe-detail view ("Split workbench") into container.
 *
 * Header, one row of actions led by Start cooking, then the ingredients card
 * beside the method. Below 720px (container query) the two become tabs.
 * @param {HTMLElement} container
 * @param {string} code
 * @param {{ returnTo: string }} options route hash the back link returns to
 * @returns {Promise<void>}
 */
export async function renderDetail(container, code, { returnTo }) {
  // Opened from inside the app, the index already has the header: show it now
  // and fill in the rest when the full recipe lands.
  const index = peekRecipeIndex();
  const cover = index ? indexedRecipe(index, code) : undefined;
  if (cover) {
    const loading = document.createElement("p");
    loading.className = "state-msg";
    loading.setAttribute("role", "status");
    loading.textContent = "Loading the recipe…";
    container.replaceChildren(page(buildBack(returnTo), buildHeader(cover, null), loading));
  }

  const recipe = await getRecipe(code);
  const layout = layoutIngredients(recipe.ingredients);
  // Cooking mode, Copy and Export all use the servings set in the card.
  let ratio = 1;

  const status = document.createElement("div");
  status.className = "rd-status";
  status.setAttribute("aria-live", "polite");
  let statusTimer = 0;
  /** @param {string} message */
  const announce = (message) => {
    status.textContent = message;
    window.clearTimeout(statusTimer);
    statusTimer = window.setTimeout(() => {
      status.textContent = "";
    }, STATUS_MS);
  };

  const notes = buildNotes(recipe);
  const method = buildMethod(recipe, notes.element);
  const ingredients = IngredientsCard({
    layout,
    baseServings: recipe.base_servings,
    onRatioChange: (next) => {
      ratio = next;
    },
    onAnnounce: announce,
  });

  const body = document.createElement("div");
  body.className = "rd-body";
  body.append(ingredients, method);
  const tabs = buildTabs(body, layout.count, recipe.instructions.length);

  const actions = RecipeActions({
    recipe,
    onStartCooking: recipe.instructions.length > 0 ? () => startCooking(recipe, ratio) : null,
    recipeText: () => formatRecipe(recipe, layout, ratio),
    menuItems: () => [
      {
        glyph: "↗",
        label: "Copy share link",
        onSelect: () => copyShareLink(recipe, announce),
      },
      {
        glyph: "✎",
        label: notes.isOpen() ? "Hide notes" : notes.hasText() ? "Show notes" : "Add a note",
        onSelect: () => {
          // On a phone the notes sit in the Method tab.
          tabs.select("method");
          notes.setOpen(!notes.isOpen());
        },
      },
    ],
    onAnnounce: announce,
  });

  container.replaceChildren(
    page(
      buildBack(returnTo),
      buildHeader(recipe, recipe),
      ...optional(buildDescription(recipe)),
      ...optional(buildChips(recipe)),
      buildSource(recipe),
      actions,
      status,
      tabs.element,
      body,
    ),
  );
}

/**
 * The query container plus its single child: container queries style only
 * descendants, so the layout hangs off the inner element.
 * @param {...HTMLElement} children
 * @returns {HTMLElement}
 */
function page(...children) {
  const outer = document.createElement("article");
  outer.className = "rd";
  const inner = document.createElement("div");
  inner.className = "rd__page";
  inner.append(...children);
  outer.append(inner);
  return outer;
}

/**
 * @param {HTMLElement | null} element
 * @returns {HTMLElement[]}
 */
function optional(element) {
  return element === null ? [] : [element];
}

/**
 * @param {string} returnTo
 * @returns {HTMLAnchorElement}
 */
function buildBack(returnTo) {
  const back = document.createElement("a");
  back.className = "rd__back";
  back.href = `#${returnTo}`;
  back.textContent = `← Back to ${returnTo.split("/")[0]}`;
  return back;
}

/* ---- Header ------------------------------------------------------------- */

/**
 * Thumbnail (only when there is a photo), kicker, title and meta. While the
 * full recipe loads, `recipe` is null and only the cover fields show.
 * @param {CoverFields} cover
 * @param {RecipeDetail | null} recipe
 * @returns {HTMLElement}
 */
function buildHeader(cover, recipe) {
  const header = document.createElement("header");
  header.className = "rd-head";

  const src = cover.cloudinary_url ?? cover.thumbnail_url;
  if (src) {
    const img = document.createElement("img");
    img.className = "rd-head__thumb";
    img.src = src;
    img.alt = "";
    header.append(img);
  }

  const block = document.createElement("div");
  block.className = "rd-head__text";
  if (recipe !== null) {
    const kicker = [recipe.cuisine_type, recipe.course]
      .filter(hasValue)
      .map(humanise)
      .join(" · ");
    if (kicker) {
      const eyebrow = document.createElement("div");
      eyebrow.className = "rd-head__kicker";
      eyebrow.textContent = kicker;
      block.append(eyebrow);
    }
  }
  block.append(...buildTitle(cover));
  if (recipe !== null) {
    block.append(buildMeta(recipe));
  }
  header.append(block);
  return header;
}

/**
 * The h1, plus the subtitle a "(…)" in the title turns into. A stand-in for
 * a missing title gets none of that flourish — it is not a name.
 * @param {CoverFields} recipe
 * @returns {HTMLElement[]}
 */
function buildTitle(recipe) {
  const h1 = document.createElement("h1");
  h1.className = "rd-head__title";
  if (recipe.title === null) {
    h1.classList.add("rd-head__title--untitled");
    h1.textContent = displayTitle(recipe);
    return [h1];
  }

  const parts = splitTitle(recipe.title);
  h1.append(document.createTextNode(parts.lead));
  if (parts.emphasis) {
    const em = document.createElement("em");
    em.textContent = parts.emphasis;
    h1.append(em);
  }
  if (!parts.subtitle) {
    return [h1];
  }
  const subtitle = document.createElement("p");
  subtitle.className = "rd-head__subtitle";
  subtitle.textContent = parts.subtitle;
  return [h1, subtitle];
}

/**
 * "⏱ 30 min + 15 min · serves 6 · Easy · Lunch", skipping what is missing.
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildMeta(recipe) {
  const meta = document.createElement("div");
  meta.className = "rd-head__meta";
  const time = [recipe.prep_time, recipe.cook_time].filter(Boolean).join(" + ");
  const parts = [
    time ? `⏱ ${time}` : "",
    recipe.base_servings === null ? "" : `serves ${recipe.base_servings}`,
    hasValue(recipe.difficulty) ? capitalise(humanise(recipe.difficulty)) : "",
    hasValue(recipe.meal_type) ? capitalise(humanise(recipe.meal_type)) : "",
  ];
  for (const part of parts.filter(Boolean)) {
    const span = document.createElement("span");
    span.textContent = part;
    meta.append(span);
  }
  return meta;
}

/**
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement | null}
 */
function buildDescription(recipe) {
  if (!recipe.summary) {
    return null;
  }
  const p = document.createElement("p");
  p.className = "rd__description";
  p.textContent = recipe.summary;
  return p;
}

/**
 * One chip per Mediterranean category it counts toward, then at most two
 * diet chips. The rest of the taxonomy stays off this page.
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement | null}
 */
function buildChips(recipe) {
  const categories = [...new Set(recipe.mediterranean_categories.map((c) => c.category))];
  const tags = new Set(recipe.dietary_tags);
  const diets = DIET_CHIPS.filter(
    ([tag]) => tags.has(tag) && !(tag === "vegetarian" && tags.has("vegan")),
  );
  if (categories.length === 0 && diets.length === 0) {
    return null;
  }
  const row = document.createElement("div");
  row.className = "rd__chips";
  row.append(...categories.map((category) => CategoryChip(category)));
  for (const [, label] of diets.slice(0, MAX_DIET_CHIPS)) {
    const chip = document.createElement("span");
    chip.className = "rd__diet";
    chip.textContent = label;
    row.append(chip);
  }
  return row;
}

/**
 * "Saved from @handle on Instagram · View original ↗", or the hand-written
 * line for a recipe made in Dispensa (by hand or through Claude).
 * @param {RecipeDetail} recipe
 * @returns {HTMLElement}
 */
function buildSource(recipe) {
  const line = document.createElement("p");
  line.className = "rd__source";
  if (recipe.source === "manual") {
    line.textContent = "Your own recipe, written in Dispensa";
    return line;
  }
  line.append(document.createTextNode("Saved from "));
  if (recipe.author_username) {
    const handle = document.createElement("b");
    handle.className = "rd__handle";
    handle.textContent = `@${recipe.author_username}`;
    line.append(handle, document.createTextNode(" on "));
  }
  const link = document.createElement("a");
  link.href = `https://www.instagram.com/p/${encodeURIComponent(recipe.code)}/`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.textContent = "View original ↗";
  line.append(document.createTextNode("Instagram · "), link);
  return line;
}

/**
 * Copy this recipe's own page link. The page and its detail fetch are both
 * reachable without the site password (see api_auth.py).
 * @param {RecipeDetail} recipe
 * @param {(message: string) => void} announce
 * @returns {Promise<void>}
 */
async function copyShareLink(recipe, announce) {
  const url = `${window.location.origin}/#recipe/${encodeURIComponent(recipe.code)}`;
  try {
    await navigator.clipboard.writeText(url);
    announce("Share link copied");
  } catch {
    announce("Couldn't copy — your browser blocked the clipboard.");
  }
}

/**
 * The whole recipe as plain text, at the servings set in the card.
 * @param {RecipeDetail} recipe
 * @param {IngredientLayout} layout
 * @param {number} ratio
 * @returns {string}
 */
function formatRecipe(recipe, layout, ratio) {
  const lines = [displayTitle(recipe)];
  if (recipe.base_servings !== null) {
    lines.push(`Serves ${formatQuantity(recipe.base_servings * ratio)}`);
  }
  for (const section of layout.sections) {
    lines.push("", section.name || "Ingredients");
    lines.push(...section.rows.map((row) => `- ${rowText(row, ratio)}`));
    lines.push(...section.toTaste.map((item) => `- ${item}`));
  }
  if (layout.equipment.length > 0) {
    lines.push("", "Equipment", ...layout.equipment.map((item) => `- ${item}`));
  }
  if (recipe.instructions.length > 0) {
    lines.push("", "Method");
    recipe.instructions.forEach((step, i) => {
      const parsed = parseStep(step, i);
      lines.push(`${i + 1}. ${parsed.title ? `${parsed.title}. ` : ""}${parsed.body}`);
    });
  }
  return `${lines.join("\n")}\n`;
}

/* ---- Body: tabs (phone), method, notes ---------------------------------- */

/**
 * The phone's Ingredients | Method switch. CSS shows it, and hides the
 * inactive section, only below 720px; on a wide page it is inert.
 * @param {HTMLElement} body
 * @param {number} ingredientCount
 * @param {number} stepCount
 * @returns {{ element: HTMLElement, select: (key: "ingredients" | "method") => void }}
 */
function buildTabs(body, ingredientCount, stepCount) {
  const bar = document.createElement("div");
  bar.className = "rd-tabs";
  bar.setAttribute("role", "tablist");
  bar.setAttribute("aria-label", "Recipe sections");

  const tabs = /** @type {const} */ ([
    ["ingredients", `Ingredients · ${ingredientCount}`],
    ["method", `Method · ${stepCount}`],
  ]).map(([key, label]) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "rd-tabs__tab";
    tab.setAttribute("role", "tab");
    tab.textContent = label;
    tab.addEventListener("click", () => select(key));
    return { key, tab };
  });
  bar.append(...tabs.map(({ tab }) => tab));
  select("ingredients");
  return { element: bar, select };

  /**
   * @param {"ingredients" | "method"} key
   */
  function select(key) {
    body.dataset.tab = key;
    for (const { key: k, tab } of tabs) {
      tab.setAttribute("aria-selected", String(k === key));
      tab.tabIndex = k === key ? 0 : -1;
    }
  }
}

/**
 * @param {RecipeDetail} recipe
 * @param {HTMLElement} notes
 * @returns {HTMLElement}
 */
function buildMethod(recipe, notes) {
  const section = document.createElement("section");
  section.className = "rd-method";
  section.setAttribute("aria-label", "Method");

  const heading = document.createElement("h2");
  heading.className = "rd-method__title";
  heading.textContent = "Method";
  section.append(heading);

  if (recipe.instructions.length === 0) {
    const note = document.createElement("p");
    note.className = "rd-method__empty";
    note.textContent =
      recipe.source === "instagram"
        ? "No method was saved with this post. Open the original on Instagram for the steps, or cook it from the ingredient list."
        : "No method was written for this recipe yet.";
    section.append(note, notes);
    return section;
  }

  const list = document.createElement("ol");
  list.className = "rd-method__list";
  recipe.instructions.forEach((step, index) => {
    const parsed = parseStep(step, index);
    const item = document.createElement("li");
    item.className = "rd-method__step";
    const num = document.createElement("span");
    num.className = "rd-method__num";
    num.setAttribute("aria-hidden", "true");
    num.textContent = String(index + 1);
    const text = document.createElement("p");
    text.className = "rd-method__text";
    if (parsed.title) {
      const title = document.createElement("b");
      title.className = "rd-method__step-title";
      title.textContent = `${parsed.title}.`;
      text.append(title, document.createTextNode(" "));
    }
    text.append(document.createTextNode(parsed.body));
    item.append(num, text);
    list.append(item);
  });
  section.append(list, notes);
  return section;
}

/**
 * @typedef {object} Notes
 * @property {HTMLElement} element
 * @property {() => boolean} isOpen
 * @property {() => boolean} hasText
 * @property {(open: boolean) => void} setOpen
 */

/**
 * "Your notes", saved as you type. Shown when a note exists or when opened
 * from the ⋯ menu.
 * @param {RecipeDetail} recipe
 * @returns {Notes}
 */
function buildNotes(recipe) {
  const section = document.createElement("section");
  section.className = "rd-notes";
  section.setAttribute("aria-label", "Your notes");

  const heading = document.createElement("h3");
  heading.className = "rd-notes__title";
  heading.textContent = "Your notes";

  const textarea = document.createElement("textarea");
  textarea.className = "rd-notes__input";
  textarea.rows = 4;
  textarea.value = recipe.user_notes ?? "";
  textarea.placeholder = "What you’d change next time…";
  textarea.setAttribute("aria-label", "Your notes");

  const helper = document.createElement("p");
  helper.className = "rd-notes__helper";
  helper.setAttribute("aria-live", "polite");
  const idle = "Saved as you type";
  helper.textContent = idle;

  let saved = textarea.value;
  let timer = 0;
  textarea.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(save, NOTES_DEBOUNCE_MS);
  });
  // Clicking away (a link, the back button) mid-debounce must not lose the
  // last words typed.
  textarea.addEventListener("blur", () => {
    window.clearTimeout(timer);
    void save();
  });

  section.append(heading, textarea, helper);
  section.hidden = saved === "";

  return {
    element: section,
    isOpen: () => !section.hidden,
    hasText: () => textarea.value !== "",
    setOpen: (open) => {
      section.hidden = !open;
      if (open) {
        textarea.focus();
      }
    },
  };

  async function save() {
    const text = textarea.value;
    if (text === saved) {
      return;
    }
    try {
      await updateRecipe(recipe.code, { user_notes: text });
      saved = text;
      helper.textContent = idle;
    } catch {
      helper.textContent = "Couldn't save — it will retry as you type.";
    }
  }
}
