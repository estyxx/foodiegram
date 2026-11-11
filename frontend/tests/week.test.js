import assert from "node:assert/strict";
import { test } from "node:test";

import { DEFAULT_PORTIONS, addDays, isoDate } from "../js/lib/week.js";

test("isoDate formats a Date as YYYY-MM-DD", () => {
  assert.equal(isoDate(new Date(2024, 0, 1)), "2024-01-01");
});

test("addDays crosses month and leap-year boundaries", () => {
  assert.equal(addDays("2024-01-01", 7), "2024-01-08");
  assert.equal(addDays("2024-03-01", -1), "2024-02-29");
});

test("DEFAULT_PORTIONS is two", () => {
  assert.equal(DEFAULT_PORTIONS, 2);
});
