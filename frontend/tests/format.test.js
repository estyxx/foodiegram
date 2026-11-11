import assert from "node:assert/strict";
import { test } from "node:test";

import { capitalise, displayTitle, hasValue, humanise } from "../js/lib/format.js";

test("capitalise upper-cases only the first letter", () => {
  assert.equal(capitalise("hello"), "Hello");
  assert.equal(capitalise(""), "");
});

test("humanise turns underscores into spaces", () => {
  assert.equal(humanise("red_meat"), "red meat");
});

test("displayTitle falls back to the author, then a placeholder", () => {
  assert.equal(displayTitle({ title: "Ragù", author_username: "x" }), "Ragù");
  assert.equal(displayTitle({ title: null, author_username: "bob" }), "@bob");
  assert.equal(displayTitle({ title: null, author_username: null }), "Untitled save");
});

test("hasValue rejects empty and unknown enums", () => {
  assert.equal(hasValue("pasta"), true);
  assert.equal(hasValue("unknown"), false);
  assert.equal(hasValue(null), false);
});
