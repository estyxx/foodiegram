// @ts-check

/**
 * @typedef {object} CategoryTokens
 * @property {string} label
 * @property {string} dot CSS custom-property name for the swatch colour.
 * @property {string} bg CSS custom-property name for the chip background.
 * @property {string} fg CSS custom-property name for the chip foreground.
 * @property {string} tint CSS custom-property name for the band tint.
 * @property {boolean} [ring] Render the dot as an outline (eggs, processed).
 */

/**
 * The 8 Mediterranean categories mapped to design tokens (see tokens.css),
 * in the same order as the weekly targets table (domain/planning.py).
 */
export const CATEGORY = /** @type {Record<string, CategoryTokens>} */ ({
  fish: { label: "Fish", dot: "--cat-fish", bg: "--cat-fish-bg", fg: "--cat-fish-fg", tint: "--cat-fish-tint" },
  legumes: { label: "Legumes", dot: "--cat-legumes", bg: "--cat-legumes-bg", fg: "--cat-legumes-fg", tint: "--cat-legumes-tint" },
  plant_protein: { label: "Plant protein", dot: "--cat-plant", bg: "--cat-plant-bg", fg: "--cat-plant-fg", tint: "--cat-plant-tint", ring: true },
  poultry: { label: "Poultry", dot: "--cat-poultry", bg: "--cat-poultry-bg", fg: "--cat-poultry-fg", tint: "--cat-poultry-tint" },
  eggs: { label: "Eggs", dot: "--cat-eggs", bg: "--cat-eggs-bg", fg: "--cat-eggs-fg", tint: "--cat-eggs-tint", ring: true },
  dairy: { label: "Dairy", dot: "--cat-dairy", bg: "--cat-dairy-bg", fg: "--cat-dairy-fg", tint: "--cat-dairy-tint" },
  red_meat: { label: "Red meat", dot: "--cat-red-meat", bg: "--cat-red-meat-bg", fg: "--cat-red-meat-fg", tint: "--cat-red-meat-tint" },
  processed_meat: { label: "Processed", dot: "--cat-processed", bg: "--cat-processed-bg", fg: "--cat-processed-fg", tint: "--cat-processed-tint", ring: true },
});
