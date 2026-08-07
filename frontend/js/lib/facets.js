// @ts-check

/** @typedef {import("./filters.js").SelectKey} SelectKey */
/** @typedef {import("./filters.js").Segment} Segment */

/**
 * @typedef {object} ProteinPill
 * @property {string} value MedCategory value sent as `protein_category`.
 * @property {string} label
 * @property {string} color CSS custom property naming the swatch colour.
 * @property {boolean} [ring] Draw the dot as an outline (the second hue member).
 */

/**
 * @typedef {object} Tier
 * @property {string} id
 * @property {string} label
 * @property {ProteinPill[]} pills
 */

/**
 * @typedef {object} SelectSpec
 * @property {SelectKey} key
 * @property {string} label
 * @property {string[]} values Enum values, in enum order; "" (Any) is added.
 */

/**
 * @typedef {object} SegmentSpec
 * @property {Segment} value
 * @property {string} label
 * @property {string} short Narrow-screen label; three full ones wrap to two rows.
 * @property {string} hint What this tier lets in, shown under the control.
 */

/**
 * The three tiers of the library, tightest first, as a ladder of strictness.
 *
 * Named for what they promise you rather than for a property of the row:
 * "ready to cook" is the question you are actually asking. Each step down
 * says what it lets in, because "all recipes" on its own does not tell you
 * that it includes the ones we failed to extract.
 * @type {SegmentSpec[]}
 */
export const SEGMENTS = [
  {
    value: "complete",
    label: "Ready to cook",
    short: "Ready",
    hint: "Has both ingredients and a method.",
  },
  {
    value: "recipes",
    label: "All recipes",
    short: "Recipes",
    hint: "Adds recipes still missing their ingredients or method.",
  },
  {
    value: "all",
    label: "All saves",
    short: "All",
    hint: "Adds photo-only saves that are not recipes at all.",
  },
];

/** The protein key grouped by how often it belongs in a week (domain/proteins.py). */
export const TIERS = /** @type {Tier[]} */ ([
  {
    id: "tier-eat-freely",
    label: "Eat freely",
    pills: [
      { value: "fish", label: "Fish", color: "--cat-fish" },
      { value: "legumes", label: "Legumes", color: "--cat-legumes" },
      { value: "plant_protein", label: "Plant protein", color: "--cat-plant", ring: true },
    ],
  },
  {
    id: "tier-moderate",
    label: "Moderate",
    pills: [
      { value: "poultry", label: "Poultry", color: "--cat-poultry" },
      { value: "eggs", label: "Eggs", color: "--cat-eggs", ring: true },
      { value: "dairy", label: "Dairy", color: "--cat-dairy" },
    ],
  },
  {
    id: "tier-occasional",
    label: "Occasional",
    pills: [
      { value: "red_meat", label: "Red meat", color: "--cat-red-meat" },
      { value: "processed_meat", label: "Processed", color: "--cat-processed", ring: true },
    ],
  },
]);

/* The closed sets mirror domain/enums.py, minus "unknown" — filtering by "we do
 * not know" is not a question anyone asks. Dietary tags are an open list, so
 * these are the ones extraction actually emits. */
export const SELECTS = /** @type {SelectSpec[]} */ ([
  {
    key: "dishType",
    label: "Dish type",
    values: [
      "soup", "salad", "main_course", "side_dish", "dessert", "beverage", "bread",
      "sauce", "snack", "pasta", "risotto", "pizza", "sandwich", "pastry",
    ],
  },
  {
    key: "mealType",
    label: "Meal",
    values: ["breakfast", "lunch", "dinner", "snack", "dessert", "appetizer"],
  },
  {
    key: "cuisine",
    label: "Cuisine",
    values: [
      "italian", "asian", "korean", "mexican", "mediterranean", "american",
      "french", "fusion", "other",
    ],
  },
  { key: "difficulty", label: "Difficulty", values: ["easy", "medium", "hard"] },
  {
    key: "dietaryTag",
    label: "Dietary",
    values: [
      "vegetarian", "vegan", "pescatarian", "gluten_free", "dairy_free",
      "low_carb", "keto", "paleo",
    ],
  },
]);

/**
 * The heading a dropdown carries in the panel, so a message elsewhere can name
 * the filter with the same words the control used.
 * @param {SelectKey} key
 * @returns {string}
 */
export function selectLabel(key) {
  return SELECTS.find((spec) => spec.key === key)?.label ?? key;
}

/**
 * @param {string} value MedCategory value.
 * @returns {string}
 */
export function proteinLabel(value) {
  for (const tier of TIERS) {
    for (const pill of tier.pills) {
      if (pill.value === value) {
        return pill.label;
      }
    }
  }
  return value;
}

/**
 * @param {Segment} value
 * @returns {string}
 */
export function segmentHint(value) {
  return SEGMENTS.find((spec) => spec.value === value)?.hint ?? "";
}

/**
 * @param {Segment} value
 * @returns {string}
 */
export function segmentLabel(value) {
  return SEGMENTS.find((spec) => spec.value === value)?.label ?? value;
}

/**
 * The tiers looser than this one, tightest first.
 * @param {Segment} value
 * @returns {Segment[]}
 */
export function widerThan(value) {
  const index = SEGMENTS.findIndex((spec) => spec.value === value);
  return SEGMENTS.slice(index + 1).map((spec) => spec.value);
}

/**
 * How many recipes a tier holds in a set of counts.
 * @param {import("../api/client.js").RecipeCounts} counts
 * @param {Segment} segment
 * @returns {number}
 */
export function segmentCount(counts, segment) {
  if (segment === "complete") {
    return counts.complete;
  }
  return segment === "recipes" ? counts.recipes : counts.all_saves;
}
