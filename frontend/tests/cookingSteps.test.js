import assert from "node:assert/strict";
import { test } from "node:test";

import {
  formatClock,
  formatDuration,
  mentionsIngredient,
} from "../js/lib/cookingSteps.js";

test("formatDuration reads seconds, minutes and hours", () => {
  assert.equal(formatDuration(30), "30 sec");
  assert.equal(formatDuration(120), "2 min");
});

test("formatClock counts down as m:ss", () => {
  assert.equal(formatClock(65), "1:05");
  assert.equal(formatClock(5), "0:05");
});

test("mentionsIngredient matches on the distinctive words", () => {
  assert.equal(mentionsIngredient("salmon fillet", "Add the salmon"), true);
  assert.equal(mentionsIngredient("basil", "Add the salmon"), false);
});
