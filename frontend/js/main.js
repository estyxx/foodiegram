// @ts-check

import { getVersion } from "./api/client.js";
import { renderBrowse } from "./views/browse.js";
import { renderDetail } from "./views/detail.js";
import { renderPantry } from "./views/pantry.js";
import { renderPlan } from "./views/plan.js";

const view = requireElement("view");

/** Pages a recipe can be opened from; anything else falls back to browse. */
const RETURN_ROUTES = new Set(["browse", "favourites", "plan"]);

/** Last page route, so a recipe's back link returns to where it was opened. */
let returnTo = "browse";

/**
 * @param {string} id
 * @returns {HTMLElement}
 */
function requireElement(id) {
  const el = document.getElementById(id);
  if (el === null) {
    throw new Error(`Missing #${id} element`);
  }
  return el;
}

/** Render the view for the current location hash. */
async function route() {
  const hash = window.location.hash.slice(1) || "browse";
  const [name, param] = hash.split("/");
  markActiveNav(name);
  if (name !== "recipe") {
    returnTo = RETURN_ROUTES.has(name) ? hash : "browse";
  }
  view.replaceChildren();
  view.focus();

  try {
    if (name === "recipe" && param) {
      await renderDetail(view, param, { returnTo });
    } else if (name === "plan") {
      await renderPlan(view);
    } else if (name === "pantry") {
      await renderPantry(view);
    } else if (name === "favourites") {
      await renderBrowse(view, { favourites: true });
    } else {
      await renderBrowse(view, { favourites: false });
    }
  } catch (error) {
    renderError(error);
  }
}

/**
 * @param {string} name
 */
function markActiveNav(name) {
  const active = name === "recipe" ? "" : name;
  for (const link of document.querySelectorAll(".app-nav__link")) {
    const isActive = link.getAttribute("data-route") === active;
    link.classList.toggle("app-nav__link--active", isActive);
  }
}

/**
 * @param {unknown} error
 */
function renderError(error) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  const el = document.createElement("p");
  el.className = "state-msg state-msg--error";
  el.textContent = message;
  view.replaceChildren(el);
}

/**
 * Populate the footer with the deployed commit, once at startup. The package
 * version is never bumped, so the commit is what identifies a build.
 */
async function showVersion() {
  const el = document.getElementById("app-version");
  if (el === null) {
    return;
  }
  try {
    const info = await getVersion();
    el.textContent = info.commit && info.commit !== "unknown" ? info.commit : "";
  } catch {
    el.textContent = "";
  }
}

window.addEventListener("hashchange", route);
route();
showVersion();
