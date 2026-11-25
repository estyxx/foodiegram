// @ts-check

/** @typedef {import("../api/client.js").VersionInfo} VersionInfo */

/**
 * The identity of a deployed build: its commit, else the platform's deployment
 * id, else the version number. Two builds differ exactly when these differ.
 * @param {VersionInfo} info
 * @returns {string}
 */
export function buildId(info) {
  return info.commit || info.deployment || info.version;
}

/**
 * True when the server now runs a different build from the one this page
 * started with, so the page's code is out of date.
 * @param {string} loaded the build this page started with ("" if unknown)
 * @param {string} live the build the server runs now
 * @returns {boolean}
 */
export function isNewBuild(loaded, live) {
  return loaded !== "" && live !== "" && loaded !== live;
}
