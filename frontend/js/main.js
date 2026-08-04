// @ts-check

import { getVersion } from "./api/client.js";
import { renderBrowse } from "./views/browse.js";
import { renderDetail } from "./views/detail.js";

const view = requireElement("view");

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
  view.replaceChildren();
  view.focus();

  try {
    if (name === "recipe" && param) {
      await renderDetail(view, param);
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

/** Populate the footer with the deployed version, once at startup. */
async function showVersion() {
  const el = document.getElementById("app-version");
  if (el === null) {
    return;
  }
  try {
    const info = await getVersion();
    const commit =
      info.commit && info.commit !== "unknown" ? ` \u00b7 ${info.commit}` : "";
    el.textContent = `v${info.version}${commit}`;
  } catch {
    el.textContent = "";
  }
}

window.addEventListener("hashchange", route);
route();
showVersion();
