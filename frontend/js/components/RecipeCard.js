// @ts-check

import { Chip } from "./Chip.js";
import { hasValue } from "../lib/format.js";

/** @typedef {import("../api/client.js").RecipeSummary} RecipeSummary */

/**
 * A browse-grid recipe card: image, favourite toggle, serif title, meta chips.
 * @param {RecipeSummary} recipe
 * @param {{ onToggleFavourite: (recipe: RecipeSummary) => void }} handlers
 * @returns {HTMLElement}
 */
export function RecipeCard(recipe, handlers) {
  const card = document.createElement("article");
  card.className = "recipe-card";

  card.append(buildMedia(recipe, handlers.onToggleFavourite), buildBody(recipe));
  return card;
}

/**
 * @param {RecipeSummary} recipe
 * @param {(recipe: RecipeSummary) => void} onToggleFavourite
 * @returns {HTMLElement}
 */
function buildMedia(recipe, onToggleFavourite) {
  const media = document.createElement("div");
  media.className = "recipe-card__media";

  const src = recipe.cloudinary_url ?? recipe.thumbnail_url;
  if (src) {
    const img = document.createElement("img");
    img.className = "recipe-card__img";
    img.src = src;
    img.alt = recipe.title;
    img.loading = "lazy";
    media.append(img);
  }

  media.append(buildFavButton(recipe, onToggleFavourite));
  return media;
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
  if (recipe.is_favorite) {
    button.classList.add("recipe-card__fav--active");
  }
  button.textContent = recipe.is_favorite ? "\u2605" : "\u2606";
  button.addEventListener("click", () => onToggleFavourite(recipe));
  return button;
}

/**
 * @param {RecipeSummary} recipe
 * @returns {HTMLElement}
 */
function buildBody(recipe) {
  const body = document.createElement("div");
  body.className = "recipe-card__body";

  const link = document.createElement("a");
  link.className = "recipe-card__link";
  link.href = `#recipe/${recipe.code}`;

  const title = document.createElement("h3");
  title.className = "recipe-card__title";
  title.textContent = recipe.title;
  link.append(title);
  body.append(link);

  const meta = document.createElement("div");
  meta.className = "recipe-card__meta";
  for (const value of [recipe.cuisine_type, recipe.difficulty, recipe.meal_type]) {
    if (hasValue(value)) {
      meta.append(Chip(value));
    }
  }
  if (meta.childElementCount > 0) {
    body.append(meta);
  }

  return body;
}
