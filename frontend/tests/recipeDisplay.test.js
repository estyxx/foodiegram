import assert from "node:assert/strict";
import { test } from "node:test";

import { formatAmount, splitTitle } from "../js/lib/recipeDisplay.js";

test("formatAmount scales a single value, or a range", () => {
  assert.equal(formatAmount({ value: 100, high: null }, 2), "200");
  assert.equal(formatAmount({ value: 100, high: 150 }, 2), "200–300");
});

test("splitTitle keeps a one-word title as the emphasis", () => {
  assert.deepEqual(splitTitle("Risotto"), {
    lead: "",
    emphasis: "Risotto",
    subtitle: "",
  });
});
