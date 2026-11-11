import assert from "node:assert/strict";
import { test } from "node:test";

import { extractNumber, scaleIngredient } from "../js/lib/scale.js";

test("extractNumber reads the first number, or null", () => {
  assert.equal(extractNumber("200g salmon"), 200);
  assert.equal(extractNumber("a pinch of salt"), null);
});

test("scaleIngredient multiplies every number", () => {
  assert.equal(scaleIngredient("2 eggs", 2), "4 eggs");
  assert.equal(scaleIngredient("100 g flour", 0.5), "50 g flour");
});
