// @ts-check

/**
 * What the shell shows: the full app, a public recipe for a visitor, the
 * signed-out landing page, or one of the three sign-in problems.
 * @typedef {"app" | "shared" | "landing" | "not_allowed" | "failed" | "offline"} ShellState
 */

/**
 * @typedef {object} SessionInfo
 * @property {boolean} signed_in
 * @property {string} [email]
 */

/**
 * @typedef {object} ShellInputs
 * @property {SessionInfo | null} session null when the server has no web login
 * @property {boolean} reachable false when the session check could not reach the server
 * @property {string} hash the location hash, e.g. "#recipe/ABC"
 * @property {string | null} authError the ?auth_error value a failed sign-in returns with
 * @property {boolean} wasSignedIn whether this browser was signed in last time
 */

/**
 * True for a recipe page, the one route a visitor may open.
 * @param {string} hash
 * @returns {boolean}
 */
export function isRecipeRoute(hash) {
  return hash.startsWith("#recipe/") && hash.length > "#recipe/".length;
}

/**
 * Decide what to show once the session check has answered (or failed).
 * @param {ShellInputs} inputs
 * @returns {ShellState}
 */
export function shellStateFor({ session, reachable, hash, authError, wasSignedIn }) {
  if (authError === "not_allowed") {
    return "not_allowed";
  }
  if (authError === "failed") {
    return "failed";
  }
  if (!reachable) {
    // Offline but known: open the app on its cached data (the shopping list
    // must work in the shop). Offline and unknown: say so.
    return wasSignedIn ? "app" : "offline";
  }
  if (session === null || session.signed_in) {
    return "app";
  }
  return isRecipeRoute(hash) ? "shared" : "landing";
}

/**
 * The letter shown in the avatar disc.
 * @param {string} email
 * @returns {string}
 */
export function accountInitial(email) {
  const first = email.trim().charAt(0);
  return first === "" ? "·" : first.toUpperCase();
}

/**
 * Which navigation entry a route lights up; "" for none (a recipe page).
 * @param {string} name the first segment of the hash route
 * @returns {string}
 */
export function navRouteFor(name) {
  return name === "recipe" ? "" : name;
}

/** Routes that live under "More" on the phone. */
export const MORE_ROUTES = new Set(["queue", "favourites"]);
