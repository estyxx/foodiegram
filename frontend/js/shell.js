// @ts-check

import { getSession, signOut } from "./api/client.js";
import {
  MORE_ROUTES,
  accountInitial,
  navRouteFor,
  shellStateFor,
} from "./lib/shellState.js";
import { mondayOf } from "./lib/week.js";

/** @typedef {import("./lib/shellState.js").ShellState} ShellState */
/** @typedef {import("./lib/shellState.js").SessionInfo} SessionInfo */

/** Hold the progress cue back, so a fast check never flashes it. */
const CUE_DELAY_MS = 400;
/** No answer after this long is a failed sign-in check. */
const CHECK_TIMEOUT_MS = 8000;
const LOGIN_URL = "/auth/login";
/** The last known account, so an offline start can still open the app. */
const ACCOUNT_KEY = "dispensa.account";

const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * @typedef {object} Problem
 * @property {string} tag
 * @property {boolean} refused true for the garnet "not allowed" tag
 * @property {string} icon SVG path data
 * @property {string} heading
 * @property {string} text
 * @property {string} action
 */

/** @type {Record<"not_allowed" | "failed" | "offline", Problem>} */
const PROBLEMS = {
  not_allowed: {
    tag: "Not allowed",
    refused: true,
    icon: "M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16ZM6.5 6.5l11 11",
    heading: "This account is not allowed",
    text: "Dispensa has one owner. Sign in with the owner’s passkey or Google account.",
    action: "Use another account",
  },
  failed: {
    tag: "Not finished",
    refused: false,
    icon: "M19 12a7 7 0 1 1-2.3-5.2M19 4.5V9h-4.5",
    heading: "Sign-in did not complete",
    text: "Nothing was changed. It usually works on the second go.",
    action: "Try again",
  },
  offline: {
    tag: "Offline",
    refused: false,
    icon: "M4 9.5a12 12 0 0 1 16 0M7 13a7.5 7.5 0 0 1 10 0M10 16.3a3 3 0 0 1 4 0M4.5 4.5l15 15",
    heading: "You are offline",
    text: "Dispensa needs a connection to check who you are. It will try by itself when you are back online.",
    action: "Try again",
  },
};

/**
 * @param {string} tag
 * @param {string} className
 * @param {string} [text]
 * @returns {HTMLElement}
 */
function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/**
 * A small decorative stroke icon.
 * @param {string} path
 * @returns {SVGElement}
 */
function icon(path) {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "icon icon--sm");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  const shape = document.createElementNS(SVG_NS, "path");
  shape.setAttribute("d", path);
  svg.append(shape);
  return svg;
}

/**
 * @param {string} id
 * @returns {HTMLElement}
 */
function byId(id) {
  const node = document.getElementById(id);
  if (node === null) {
    throw new Error(`Missing #${id} element`);
  }
  return node;
}

/**
 * @returns {{ email: string } | null}
 */
function rememberedAccount() {
  try {
    const raw = window.localStorage.getItem(ACCOUNT_KEY);
    return raw === null ? null : { email: String(JSON.parse(raw).email ?? "") };
  } catch {
    return null;
  }
}

/**
 * @param {{ email: string } | null} account
 */
function rememberAccount(account) {
  try {
    if (account === null) {
      window.localStorage.removeItem(ACCOUNT_KEY);
    } else {
      window.localStorage.setItem(ACCOUNT_KEY, JSON.stringify(account));
    }
  } catch {
    // Storage blocked: an offline start will show the offline page instead.
  }
}

/**
 * Ask the server who is signed in. Resolves with `reachable: false` when the
 * network fails or the answer takes too long.
 * @returns {Promise<{ session: SessionInfo | null, reachable: boolean, timedOut: boolean }>}
 */
async function checkSession() {
  /** @type {Promise<"timeout">} */
  const timeout = new Promise((resolve) => {
    window.setTimeout(() => resolve("timeout"), CHECK_TIMEOUT_MS);
  });
  try {
    const answer = await Promise.race([getSession(), timeout]);
    if (answer === "timeout") {
      return { session: null, reachable: false, timedOut: true };
    }
    return { session: answer, reachable: true, timedOut: false };
  } catch {
    return { session: null, reachable: false, timedOut: false };
  }
}

/** Show the checking cue in the gate, once the check has been slow enough. */
function showCheckingCue() {
  const cue = el("div", "gate__cue");
  cue.setAttribute("role", "status");
  const track = el("span", "gate__track");
  track.setAttribute("aria-hidden", "true");
  track.append(el("span", "gate__segment"));
  cue.append(track, el("span", "shell-label", "Checking sign-in"));
  byId("gate-body").replaceChildren(cue);
}

function showLanding() {
  document.body.dataset.shell = "landing";
  const line = el(
    "p",
    "gate__line",
    "A personal Mediterranean recipe library and weekly meal planner.",
  );
  const button = /** @type {HTMLAnchorElement} */ (el("a", "gate__button", "Sign in"));
  button.href = LOGIN_URL;
  byId("gate-body").replaceChildren(
    line,
    button,
    el("span", "shell-label", "Passkey or Google"),
  );
}

/**
 * @param {"not_allowed" | "failed" | "offline"} kind
 */
function showProblem(kind) {
  const problem = PROBLEMS[kind];
  document.body.dataset.shell = "problem";
  const box = el("div", "gate__problem");
  box.setAttribute("role", "alert");
  const tag = el("span", "gate__tag");
  if (problem.refused) {
    tag.classList.add("gate__tag--refused");
  }
  tag.append(icon(problem.icon), document.createTextNode(problem.tag));
  const heading = el("h1", "gate__heading", problem.heading);
  heading.tabIndex = -1;
  const button = /** @type {HTMLAnchorElement} */ (
    el("a", "gate__button", problem.action)
  );
  // Offline retries the whole page; the other two go back through the login.
  button.href = kind === "offline" ? window.location.pathname : LOGIN_URL;
  box.append(tag, heading, el("p", "gate__text", problem.text), button);
  byId("gate-body").replaceChildren(box);
  heading.focus();
  if (kind === "offline") {
    window.addEventListener("online", () => window.location.reload(), { once: true });
  }
}

/**
 * Fill every account slot with the signed-in email and wire sign-out.
 * @param {string} email
 */
function showAccount(email) {
  for (const node of document.querySelectorAll("[data-account-email]")) {
    node.textContent = email;
  }
  for (const node of document.querySelectorAll("[data-account-initial]")) {
    node.textContent = accountInitial(email);
  }
  byId("account-disc").setAttribute("aria-label", `Account. Signed in as ${email}`);
  byId("account").hidden = false;
  byId("more-account").hidden = false;
  for (const button of document.querySelectorAll("[data-sign-out]")) {
    button.addEventListener("click", () => {
      rememberAccount(null);
      void signOut().finally(() => {
        window.location.assign("/");
      });
    });
  }
}

/** Wire the More sheet, the account popover and the Shop link. */
function wireNavigation() {
  const sheet = /** @type {HTMLDialogElement} */ (byId("more-sheet"));
  const more = byId("more-button");
  const open = () => {
    sheet.showModal();
    more.setAttribute("aria-expanded", "true");
  };
  more.addEventListener("click", open);
  byId("account-disc").addEventListener("click", open);
  byId("more-close").addEventListener("click", () => sheet.close());
  sheet.addEventListener("close", () => more.setAttribute("aria-expanded", "false"));
  // A tap on the scrim lands on the dialog itself, not on its contents.
  sheet.addEventListener("click", (event) => {
    if (event.target === sheet) {
      sheet.close();
    }
  });
  for (const link of sheet.querySelectorAll("a")) {
    link.addEventListener("click", () => sheet.close());
  }

  const pill = byId("account-pill");
  byId("account-menu").addEventListener("toggle", (event) => {
    const isOpen = /** @type {ToggleEvent} */ (event).newState === "open";
    pill.setAttribute("aria-expanded", String(isOpen));
  });

  const shop = `#shop/${mondayOf(new Date())}`;
  for (const link of document.querySelectorAll("[data-shop-link]")) {
    link.setAttribute("href", shop);
  }
}

/**
 * Light up the navigation entry for the current route, in the top bar, the tab
 * bar and the More sheet. More itself shows current for the routes it holds.
 * @param {string} name the first segment of the hash route
 */
export function markActiveNav(name) {
  const active = navRouteFor(name);
  for (const link of document.querySelectorAll("[data-route]")) {
    if (link.getAttribute("data-route") === active) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  }
  byId("more-button").classList.toggle("tabbar__tab--current", MORE_ROUTES.has(active));
}

/** Show the signed-out landing page (a visitor left the shared recipe). */
export function showSignedOut() {
  showLanding();
}

/**
 * Check the session and put the shell in the matching state. Resolves with the
 * state; the caller starts routing only for "app" and "shared".
 * @returns {Promise<ShellState>}
 */
export async function startShell() {
  const cueTimer = window.setTimeout(showCheckingCue, CUE_DELAY_MS);
  const params = new URLSearchParams(window.location.search);
  const authError = params.get("auth_error");
  if (authError !== null) {
    // Drop the marker so a reload does not show the problem page again.
    window.history.replaceState(null, "", window.location.pathname + window.location.hash);
  }

  const check = await checkSession();
  window.clearTimeout(cueTimer);
  const remembered = rememberedAccount();
  const state = check.timedOut
    ? "failed"
    : shellStateFor({
        session: check.session,
        reachable: check.reachable,
        hash: window.location.hash,
        authError,
        wasSignedIn: remembered !== null,
      });

  if (state === "landing") {
    rememberAccount(null);
    showLanding();
    return state;
  }
  if (state === "not_allowed" || state === "failed" || state === "offline") {
    showProblem(state);
    return state;
  }

  wireNavigation();
  if (state === "shared") {
    rememberAccount(null);
    byId("signin").hidden = false;
    /** @type {HTMLAnchorElement} */ (byId("brand")).href = "/";
  } else if (check.session?.signed_in) {
    const email = check.session.email ?? "";
    rememberAccount({ email });
    showAccount(email);
  } else if (!check.reachable && remembered !== null) {
    showAccount(remembered.email);
  }
  document.body.dataset.shell = state;
  return state;
}
