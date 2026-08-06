// @ts-check

import { capitalise, displayTitle, hasValue, humanise } from "../lib/format.js";

/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */

// Pantry match counts (have/total) need per-recipe pantry resolution we don't
// compute yet; keep the slot wired but off until that lands.
const SHOW_PANTRY_COUNTS = false;

const SVG_NS = "http://www.w3.org/2000/svg";

const PLANT_TAGS = new Set(["vegan", "vegetarian", "plant_based", "plant-based"]);

/**
 * @typedef {object} CategoryTokens
 * @property {string} label
 * @property {string} dot CSS custom-property name for the swatch colour.
 * @property {string} bg CSS custom-property name for the chip background.
 * @property {string} fg CSS custom-property name for the chip foreground.
 * @property {string} tint CSS custom-property name for the band tint.
 * @property {boolean} [ring] Render the dot as an outline (eggs, processed).
 */

/** The category key mapped to design tokens (see tokens.css). */
const CATEGORY = /** @type {Record<string, CategoryTokens>} */ ({
  fish: { label: "Fish", dot: "--cat-fish", bg: "--cat-fish-bg", fg: "--cat-fish-fg", tint: "--cat-fish-tint" },
  legumes: { label: "Legumes", dot: "--cat-legumes", bg: "--cat-legumes-bg", fg: "--cat-legumes-fg", tint: "--cat-legumes-tint" },
  plant_protein: { label: "Plant protein", dot: "--cat-plant", bg: "--cat-plant-bg", fg: "--cat-plant-fg", tint: "--cat-plant-tint", ring: true },
  poultry: { label: "Poultry", dot: "--cat-poultry", bg: "--cat-poultry-bg", fg: "--cat-poultry-fg", tint: "--cat-poultry-tint" },
  eggs: { label: "Eggs", dot: "--cat-eggs", bg: "--cat-eggs-bg", fg: "--cat-eggs-fg", tint: "--cat-eggs-tint", ring: true },
  dairy: { label: "Dairy", dot: "--cat-dairy", bg: "--cat-dairy-bg", fg: "--cat-dairy-fg", tint: "--cat-dairy-tint" },
  red_meat: { label: "Red meat", dot: "--cat-red-meat", bg: "--cat-red-meat-bg", fg: "--cat-red-meat-fg", tint: "--cat-red-meat-tint" },
  processed_meat: { label: "Processed", dot: "--cat-processed", bg: "--cat-processed-bg", fg: "--cat-processed-fg", tint: "--cat-processed-tint", ring: true },
});

/**
 * A browse-grid recipe card (Maiolica design): banded thumbnail with collection
 * chip, serif title, caption snippet, category tracks, and a meta footer.
 * @param {RecipeSummary} recipe
 * @param {{ onToggleFavourite: (recipe: RecipeSummary) => void }} handlers
 * @returns {HTMLElement}
 */
export function RecipeCard(recipe, handlers) {
  const primary = CATEGORY[recipe.mediterranean_categories[0]] ?? null;

  const card = document.createElement("article");
  card.className = "recipe-card";

  card.append(buildMedia(recipe, primary, handlers.onToggleFavourite), buildBody(recipe));
  return card;
}

/* ---- Thumbnail ---------------------------------------------------------- */

/**
 * @param {RecipeSummary} recipe
 * @param {CategoryTokens | null} primary
 * @param {(recipe: RecipeSummary) => void} onToggleFavourite
 * @returns {HTMLElement}
 */
function buildMedia(recipe, primary, onToggleFavourite) {
  const media = document.createElement("div");
  media.className = "recipe-card__media";
  media.style.setProperty(
    "--band",
    primary ? `var(${primary.tint})` : "var(--surface-tint)",
  );

  const src = recipe.cloudinary_url ?? recipe.thumbnail_url;
  if (src) {
    const img = document.createElement("img");
    img.className = "recipe-card__img";
    img.src = src;
    img.alt = displayTitle(recipe);
    img.loading = "lazy";
    media.append(img);
  } else {
    media.append(buildPlaceholder());
  }

  const collection = buildCollection(recipe, primary);
  if (collection !== null) {
    media.append(collection);
  }

  const badges = document.createElement("div");
  badges.className = "recipe-card__badges";
  if (isPlant(recipe)) {
    badges.append(buildLeaf());
  }
  badges.append(buildFavButton(recipe, onToggleFavourite));
  media.append(badges);

  return media;
}

/**
 * @returns {HTMLElement}
 */
function buildPlaceholder() {
  const wrap = document.createElement("div");
  wrap.className = "recipe-card__placeholder";
  wrap.setAttribute("aria-hidden", "true");

  const text = document.createElement("span");
  text.className = "recipe-card__placeholder-text";
  text.textContent = "No photo";

  wrap.append(buildPhotoIcon(), text);
  return wrap;
}

/**
 * @returns {SVGSVGElement}
 */
function buildPhotoIcon() {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "recipe-card__placeholder-icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.5");
  svg.setAttribute("aria-hidden", "true");

  const frame = document.createElementNS(SVG_NS, "rect");
  frame.setAttribute("x", "3");
  frame.setAttribute("y", "3");
  frame.setAttribute("width", "18");
  frame.setAttribute("height", "18");
  frame.setAttribute("rx", "2");

  const sun = document.createElementNS(SVG_NS, "circle");
  sun.setAttribute("cx", "8.5");
  sun.setAttribute("cy", "8.5");
  sun.setAttribute("r", "1.5");

  const hill = document.createElementNS(SVG_NS, "path");
  hill.setAttribute("d", "M21 15l-5-5L5 21");
  hill.setAttribute("stroke-linecap", "round");
  hill.setAttribute("stroke-linejoin", "round");

  svg.append(frame, sun, hill);
  return svg;
}

/**
 * Overlaid dish chip: category dot + the dish type, or null when unknown.
 * @param {RecipeSummary} recipe
 * @param {CategoryTokens | null} primary
 * @returns {HTMLElement | null}
 */
function buildCollection(recipe, primary) {
  const label = dishLabel(recipe);
  if (label === null) {
    return null;
  }

  const chip = document.createElement("span");
  chip.className = "recipe-card__collection";
  applyChipColors(chip, primary);

  const dot = document.createElement("span");
  dot.className = "recipe-card__collection-dot";

  const text = document.createElement("span");
  text.textContent = label;

  chip.append(dot, text);
  return chip;
}

/**
 * @returns {HTMLElement}
 */
function buildLeaf() {
  const leaf = document.createElement("span");
  leaf.className = "recipe-card__leaf";
  leaf.setAttribute("role", "img");
  leaf.setAttribute("aria-label", "Plant-based");
  leaf.textContent = "\u2767";
  return leaf;
}

/**
 * @param {RecipeSummary} recipe
 * @param {(recipe: RecipeSummary) => void} onToggleFavourite
 * @returns {HTMLButtonElement}
 */
function buildFavButton(recipe, onToggleFavourite) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "recipe-card__fav";
  const label = recipe.is_favorite ? "Remove from favourites" : "Add to favourites";
  button.setAttribute("aria-label", label);
  button.setAttribute("aria-pressed", String(recipe.is_favorite));
  button.classList.toggle("recipe-card__fav--active", recipe.is_favorite);
  button.textContent = recipe.is_favorite ? "\u2605" : "\u2606";
  button.addEventListener("click", () => onToggleFavourite(recipe));
  return button;
}

/* ---- Body --------------------------------------------------------------- */

/**
 * @param {RecipeSummary} recipe
 * @returns {HTMLElement}
 */
function buildBody(recipe) {
  const heading = displayTitle(recipe);

  const body = document.createElement("a");
  body.className = "recipe-card__body";
  body.href = `#recipe/${recipe.code}`;
  body.setAttribute("aria-label", heading);

  const title = document.createElement("h3");
  title.className = "recipe-card__title";
  title.textContent = heading;
  if (recipe.title === null) {
    title.classList.add("recipe-card__title--untitled");
  }
  body.append(title, buildDescription(recipe));

  if (recipe.mediterranean_categories.length > 0) {
    body.append(buildTracks(recipe));
  }
  body.append(buildMeta(recipe));
  return body;
}

/**
 * @param {RecipeSummary} recipe
 * @returns {HTMLElement}
 */
function buildDescription(recipe) {
  const p = document.createElement("p");
  if (recipe.description) {
    p.className = "recipe-card__desc";
    p.textContent = recipe.description;
    return p;
  }
  p.className = "recipe-card__desc recipe-card__desc--empty";
  // The handle is already the heading when there is no title; don't say it twice.
  p.textContent =
    recipe.author_username && recipe.title !== null
      ? `Saved from @${recipe.author_username} \u2014 the original post had no caption.`
      : "The original post had no caption.";
  return p;
}

/**
 * @param {RecipeSummary} recipe
 * @returns {HTMLElement}
 */
function buildTracks(recipe) {
  const wrap = document.createElement("div");
  wrap.className = "recipe-card__tracks";
  for (const key of recipe.mediterranean_categories) {
    const tokens = CATEGORY[key];
    if (!tokens) {
      continue;
    }
    const chip = document.createElement("span");
    chip.className = "recipe-card__track";
    applyChipColors(chip, tokens);

    const dot = document.createElement("span");
    dot.className = tokens.ring
      ? "recipe-card__track-dot recipe-card__track-dot--ring"
      : "recipe-card__track-dot";

    const text = document.createElement("span");
    text.textContent = tokens.label;

    chip.append(dot, text);
    wrap.append(chip);
  }
  return wrap;
}

/**
 * @param {RecipeSummary} recipe
 * @returns {HTMLElement}
 */
function buildMeta(recipe) {
  const meta = document.createElement("div");
  meta.className = "recipe-card__meta";

  const left = document.createElement("span");
  left.className = "recipe-card__meta-left";
  left.textContent = metaText(recipe);
  meta.append(left);

  if (SHOW_PANTRY_COUNTS) {
    const right = document.createElement("span");
    right.className = "recipe-card__meta-right";
    meta.append(right);
  }
  return meta;
}

/* ---- Derivations -------------------------------------------------------- */

/**
 * @param {HTMLElement} el
 * @param {CategoryTokens | null} tokens
 */
function applyChipColors(el, tokens) {
  el.style.setProperty(
    "--chip-bg",
    tokens ? `var(${tokens.bg})` : "var(--surface-tint)",
  );
  el.style.setProperty(
    "--chip-fg",
    tokens ? `var(${tokens.fg})` : "var(--ink-muted)",
  );
  el.style.setProperty("--dot", tokens ? `var(${tokens.dot})` : "var(--ink-faint)");
}

/**
 * Return the dish label for the card badge, or null to show no badge.
 *
 * Only dish_type: falling back to cuisine or "Recipe" is what made the badge
 * look random, since a quarter of recipes have no dish type. Empty beats wrong.
 * @param {RecipeSummary} recipe
 * @returns {string | null}
 */
function dishLabel(recipe) {
  return hasValue(recipe.dish_type) ? capitalise(humanise(recipe.dish_type)) : null;
}

/**
 * @param {RecipeSummary} recipe
 * @returns {string}
 */
function metaText(recipe) {
  /** @type {string[]} */
  const parts = [];
  if (hasValue(recipe.total_time)) {
    parts.push(recipe.total_time);
  }
  if (recipe.base_servings !== null) {
    parts.push(`serves ${recipe.base_servings}`);
  }
  if (hasValue(recipe.difficulty)) {
    parts.push(capitalise(humanise(recipe.difficulty)));
  }
  return parts.length > 0 ? parts.join(" \u00b7 ") : "from Instagram";
}

/**
 * @param {RecipeSummary} recipe
 * @returns {boolean}
 */
function isPlant(recipe) {
  return recipe.dietary_tags.some((tag) => PLANT_TAGS.has(tag.toLowerCase()));
}
