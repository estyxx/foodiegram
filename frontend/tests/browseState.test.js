import assert from "node:assert/strict";
import { test } from "node:test";

import { parseBrowseState } from "../js/lib/browseState.js";
import { emptyFilters } from "../js/lib/filters.js";

test("a saved search comes back as it was", () => {
  const saved = {
    filters: {
      ...emptyFilters(),
      query: "zucca",
      ingredients: ["ceci"],
      cuisine: "italian",
      segment: "recipes",
    },
    mode: "ai",
    shown: 100,
    scrollY: 1840,
  };
  assert.deepEqual(parseBrowseState(JSON.stringify(saved)), saved);
});

test("nothing saved, or junk, starts a fresh Browse", () => {
  assert.equal(parseBrowseState(null), null);
  assert.equal(parseBrowseState("{not json"), null);
  assert.equal(parseBrowseState("42"), null);
});

test("malformed fields fall back to their defaults", () => {
  const state = parseBrowseState(
    JSON.stringify({ filters: { query: 7, ingredients: "x", segment: "gone" }, mode: "?" }),
  );
  assert.ok(state);
  assert.equal(state.filters.query, "");
  assert.deepEqual(state.filters.ingredients, []);
  assert.equal(state.filters.segment, "complete");
  assert.equal(state.mode, "lexical");
  assert.equal(state.shown, 0);
  assert.equal(state.scrollY, 0);
});
