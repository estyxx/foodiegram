import assert from "node:assert/strict";
import { test } from "node:test";

import {
  accountInitial,
  isRecipeRoute,
  navRouteFor,
  shellStateFor,
} from "../js/lib/shellState.js";

/** @type {import("../js/lib/shellState.js").ShellInputs} */
const BASE = {
  session: { signed_in: false },
  reachable: true,
  hash: "",
  authError: null,
  wasSignedIn: false,
};

test("a signed-in owner gets the app", () => {
  const state = shellStateFor({ ...BASE, session: { signed_in: true, email: "a@b.c" } });
  assert.equal(state, "app");
});

test("a server without the web login shows the app as before", () => {
  assert.equal(shellStateFor({ ...BASE, session: null }), "app");
});

test("a visitor sees the landing page, or the recipe they were sent", () => {
  assert.equal(shellStateFor(BASE), "landing");
  assert.equal(shellStateFor({ ...BASE, hash: "#plan" }), "landing");
  assert.equal(shellStateFor({ ...BASE, hash: "#recipe/DJq4i8ysCL8" }), "shared");
  assert.equal(shellStateFor({ ...BASE, hash: "#recipe/" }), "landing");
});

test("a failed sign-in shows its own page, even over a valid session", () => {
  const signedIn = { ...BASE, session: { signed_in: true } };
  assert.equal(shellStateFor({ ...signedIn, authError: "not_allowed" }), "not_allowed");
  assert.equal(shellStateFor({ ...signedIn, authError: "failed" }), "failed");
  assert.equal(shellStateFor({ ...signedIn, authError: "nonsense" }), "app");
});

test("offline opens the app only for a browser that was signed in", () => {
  const offline = { ...BASE, session: null, reachable: false };
  assert.equal(shellStateFor(offline), "offline");
  assert.equal(shellStateFor({ ...offline, wasSignedIn: true }), "app");
});

test("accountInitial takes the first letter, upper-cased", () => {
  assert.equal(accountInitial("ester@example.com"), "E");
  assert.equal(accountInitial("  "), "·");
});

test("isRecipeRoute and navRouteFor", () => {
  assert.equal(isRecipeRoute("#recipe/X"), true);
  assert.equal(isRecipeRoute("#browse"), false);
  assert.equal(navRouteFor("recipe"), "");
  assert.equal(navRouteFor("shop"), "shop");
});
