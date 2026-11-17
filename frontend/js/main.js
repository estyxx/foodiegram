// @ts-check

import { RETURN_HASH_KEY, getVersion } from "./api/client.js";
import { CookingMode } from "./components/CookingMode.js";
import { CookingPill } from "./components/CookingPill.js";
import { isRecipeRoute } from "./lib/shellState.js";
import { markActiveNav, showSignedOut, startShell } from "./shell.js";
import { renderBrowse } from "./views/browse.js";
import { renderDetail } from "./views/detail.js";
import { renderPlan } from "./views/plan.js";
import { renderPantry } from "./views/pantry.js";
import { renderQueue } from "./views/queue.js";
import { renderShop } from "./views/shop.js";

const view = requireElement("view");

/** The page the app opens on. */
const HOME_ROUTE = "plan";

/** Pages a recipe can be opened from; anything else falls back to browse. */
const RETURN_ROUTES = new Set(["browse", "favourites", "plan"]);

/** Last page route, so a recipe's back link returns to where it was opened. */
let returnTo = "browse";

/** True for someone reading a shared recipe without being signed in. */
let visitor = false;

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
  if (visitor && !isRecipeRoute(window.location.hash)) {
    // A visitor may read the recipe they were sent, nothing else.
    showSignedOut();
    return;
  }
  const hash = window.location.hash.slice(1) || HOME_ROUTE;
  const [name, param] = hash.split("/");
  markActiveNav(name);
  if (name !== "recipe") {
    returnTo = RETURN_ROUTES.has(name) ? hash : "browse";
  }
  view.replaceChildren();
  view.focus();

  try {
    if (name === "recipe" && param) {
      await renderDetail(view, param, { returnTo, visitor });
    } else if (name === "plan") {
      await renderPlan(view);
    } else if (name === "shop" && param) {
      await renderShop(view, param);
    } else if (name === "pantry") {
      await renderPantry(view);
    } else if (name === "queue") {
      await renderQueue(view);
    } else if (name === "favourites") {
      await renderBrowse(view, { favourites: true });
    } else if (name === "browse") {
      await renderBrowse(view, { favourites: false });
    } else {
      await renderPlan(view);
    }
  } catch (error) {
    renderError(error);
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
    const id = info.commit || info.deployment || "";
    el.textContent = id ? `${info.version} · ${id}` : info.version;
  } catch {
    el.textContent = "";
  }
}

// Outside #view: cooking mode and its timers survive route changes.
document.body.append(CookingMode(), CookingPill());

// Register the service worker so the installed app opens and shows the last
// loaded data offline. Failures are non-fatal: the app runs without it.
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

/** After signing in, go back to the page the session ran out on. */
function restoreReturnHash() {
  try {
    const saved = window.sessionStorage.getItem(RETURN_HASH_KEY);
    window.sessionStorage.removeItem(RETURN_HASH_KEY);
    if (saved && saved.startsWith("#") && window.location.hash === "") {
      window.history.replaceState(null, "", saved);
    }
  } catch {
    // Storage blocked: stay on the home page.
  }
}

/** Check who is there, then start the app (or leave the gate showing). */
async function boot() {
  const state = await startShell();
  if (state !== "app" && state !== "shared") {
    return;
  }
  visitor = state === "shared";
  window.addEventListener("hashchange", route);
  restoreReturnHash();
  route();
  showVersion();
}

boot();
