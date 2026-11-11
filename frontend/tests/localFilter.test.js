import assert from "node:assert/strict";
import { test } from "node:test";

import { searchLocally } from "../js/lib/localFilter.js";

const INDEX = {
  synonyms: [],
  recipes: [
    { code: "A", is_recipe: true, is_complete: true, is_favorite: false },
    { code: "B", is_recipe: true, is_complete: false, is_favorite: true },
    { code: "C", is_recipe: false, is_complete: false, is_favorite: false },
  ],
};

const BASE = {
  query: "",
  ingredients: [],
  proteins: [],
  dishType: "",
  mealType: "",
  cuisine: "",
  difficulty: "",
  dietaryTag: "",
  segment: "all",
};

test("searchLocally counts the nested segments", () => {
  const out = searchLocally(INDEX, BASE, { favourites: false });
  assert.deepEqual(out.counts, { complete: 1, recipes: 2, all_saves: 3 });
  assert.equal(out.results.length, 3);
});

test("the favourites view keeps only favourite entries", () => {
  const out = searchLocally(INDEX, { ...BASE, segment: "recipes" }, { favourites: true });
  assert.deepEqual(
    out.results.map((entry) => entry.code),
    ["B"],
  );
});
