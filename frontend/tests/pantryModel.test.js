import assert from "node:assert/strict";
import { test } from "node:test";

import {
  daysToExpiry,
  expiryNote,
  expiryStatus,
  isoOffset,
  locationLabel,
  sections,
  summaryLine,
  useSoon,
} from "../js/lib/pantryModel.js";

const TODAY = new Date(2026, 10, 13); // 13 Nov 2026, local midnight.

/**
 * @param {string} name
 * @param {string} location
 * @param {string | null} expires
 * @returns {import("../js/api/client.js").PantryItem}
 */
function item(name, location, expires) {
  return { id: null, name, kind: "fresh", location, quantity: "", expires };
}

test("locationLabel maps known values and falls back to Other", () => {
  assert.equal(locationLabel("fridge"), "Fridge");
  assert.equal(locationLabel("unknown"), "Other");
  assert.equal(locationLabel("nonsense"), "Other");
});

test("daysToExpiry counts whole days, null when undated", () => {
  assert.equal(daysToExpiry(null, TODAY), null);
  assert.equal(daysToExpiry("2026-11-13", TODAY), 0);
  assert.equal(daysToExpiry("2026-11-16", TODAY), 3);
  assert.equal(daysToExpiry("2026-11-10", TODAY), -3);
});

test("expiryStatus badges only the last week", () => {
  assert.equal(expiryStatus(null, TODAY), null);
  assert.equal(expiryStatus("2026-11-30", TODAY), null); // 17 days off
  assert.equal(expiryStatus("2026-11-13", TODAY)?.short, "Use today");
  assert.equal(expiryStatus("2026-11-14", TODAY)?.short, "Tomorrow");
  assert.equal(expiryStatus("2026-11-16", TODAY)?.short, "3 days");
  const past = expiryStatus("2026-11-10", TODAY);
  assert.equal(past?.kind, "expired");
  assert.match(past?.long ?? "", /^Expired /);
});

test("sections keeps only non-empty locations, sorted A–Z", () => {
  const items = [item("Zucchina", "fridge", null), item("Avocado", "fridge", null)];
  const result = sections(items, TODAY);
  assert.equal(result.length, 1);
  assert.equal(result[0].key, "fridge");
  assert.deepEqual(
    result[0].items.map((i) => i.name),
    ["Avocado", "Zucchina"],
  );
});

test("useSoon splits soon from expired, soonest first", () => {
  const items = [
    item("Latte", "fridge", "2026-11-10"), // expired
    item("Pane", "fridge", "2026-11-14"), // tomorrow
    item("Ceci", "pantry", null), // no badge
  ];
  const { soon, expired } = useSoon(items, TODAY);
  assert.deepEqual(
    soon.map((i) => i.name),
    ["Pane"],
  );
  assert.deepEqual(
    expired.map((i) => i.name),
    ["Latte"],
  );
});

test("summaryLine counts things and the use-soon tail", () => {
  assert.equal(summaryLine([], TODAY), "Nothing on the shelves yet.");
  assert.equal(summaryLine([item("Ceci", "pantry", null)], TODAY), "1 thing on hand.");
  assert.equal(
    summaryLine([item("Pane", "fridge", "2026-11-14")], TODAY),
    "1 thing on hand · 1 to use soon.",
  );
});

test("isoOffset and expiryNote describe relative dates", () => {
  assert.equal(isoOffset(TODAY, 3), "2026-11-16");
  assert.match(expiryNote(null, TODAY), /No date set/);
  assert.match(expiryNote("2026-11-16", TODAY), /in 3 days/);
  assert.match(expiryNote("2026-11-10", TODAY), /expired 3 days ago/);
});
