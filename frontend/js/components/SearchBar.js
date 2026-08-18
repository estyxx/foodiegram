// @ts-check

const SEARCH_DEBOUNCE_MS = 200;
const SVG_NS = "http://www.w3.org/2000/svg";

const PLACEHOLDER_EMPTY = "search by ingredient: zucchine, ceci, tofu\u2026";
const PLACEHOLDER_MORE = "add another\u2026";
const PLACEHOLDER_AI = "try: something sweet for breakfast with protein\u2026";

/** @typedef {"lexical" | "ai"} SearchMode */

/**
 * @typedef {object} SearchBarHandlers
 * @property {(text: string) => void} onQueryChange Debounced free-text search.
 * @property {(term: string) => void} onAddIngredient
 * @property {(term: string) => void} onRemoveIngredient
 * @property {() => void} onToggleMode Switch between lexical and AI (semantic) search.
 */

/**
 * @typedef {object} SearchBarView
 * @property {HTMLElement} element
 * @property {(ingredients: string[], mode: SearchMode) => void} render
 */

/**
 * The search line: type to search, press Enter to pin the word as a chip.
 *
 * Free text searches one string; chips require several ingredients at once,
 * which is the difference between "find me something with squash" and "find me
 * the recipe with squash and tofu". Only the chips are re-rendered, so the
 * input keeps focus and caret while you type.
 * @param {SearchBarHandlers} handlers
 * @returns {SearchBarView}
 */
export function SearchBar(handlers) {
  /** @type {string[]} */
  let ingredients = [];
  let timer = 0;

  const field = document.createElement("div");
  field.className = "searchbar";

  const chips = document.createElement("span");
  chips.className = "searchbar__chips";

  const input = document.createElement("input");
  input.type = "text";
  input.className = "searchbar__input";
  input.autocomplete = "off";
  input.placeholder = PLACEHOLDER_EMPTY;
  input.setAttribute("aria-label", "Search recipes or ingredients");

  const hint = document.createElement("span");
  hint.className = "visually-hidden";
  hint.id = "searchbar-hint";
  hint.textContent =
    "Press Enter to require an ingredient. Backspace on an empty box removes the last one.";
  input.setAttribute("aria-describedby", hint.id);

  input.addEventListener("input", () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(
      () => handlers.onQueryChange(input.value.trim()),
      SEARCH_DEBOUNCE_MS,
    );
  });

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const term = input.value.trim();
      if (term === "") {
        return;
      }
      window.clearTimeout(timer);
      input.value = "";
      handlers.onAddIngredient(term);
      return;
    }
    const last = ingredients.at(-1);
    if (event.key === "Backspace" && input.value === "" && last !== undefined) {
      handlers.onRemoveIngredient(last);
    }
  });

  const aiToggle = document.createElement("button");
  aiToggle.type = "button";
  aiToggle.className = "searchbar__ai-toggle";
  aiToggle.setAttribute("aria-label", "AI search");
  aiToggle.setAttribute("aria-pressed", "false");
  aiToggle.textContent = "✨";
  aiToggle.addEventListener("click", () => handlers.onToggleMode());

  field.append(buildSearchIcon(), chips, input, aiToggle, hint);

  return {
    element: field,
    render(next, mode) {
      ingredients = next;
      // Removing a chip destroys the button that was clicked, so hand focus
      // back to the input before the row is rebuilt.
      chips.replaceChildren(
        ...next.map((term) =>
          buildChip(term, (value) => {
            input.focus();
            handlers.onRemoveIngredient(value);
          }),
        ),
      );
      const isAi = mode === "ai";
      aiToggle.setAttribute("aria-pressed", String(isAi));
      aiToggle.classList.toggle("searchbar__ai-toggle--active", isAi);
      input.placeholder = isAi
        ? PLACEHOLDER_AI
        : next.length > 0
          ? PLACEHOLDER_MORE
          : PLACEHOLDER_EMPTY;
    },
  };
}

/**
 * @param {string} term
 * @param {(term: string) => void} onRemove
 * @returns {HTMLElement}
 */
function buildChip(term, onRemove) {
  const chip = document.createElement("span");
  chip.className = "search-chip";

  const text = document.createElement("span");
  text.textContent = term;

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "search-chip__remove";
  remove.setAttribute("aria-label", `Remove ${term}`);
  remove.textContent = "\u00d7";
  remove.addEventListener("click", () => onRemove(term));

  chip.append(text, remove);
  return chip;
}

/**
 * @returns {SVGSVGElement}
 */
function buildSearchIcon() {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "searchbar__icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.6");
  svg.setAttribute("aria-hidden", "true");

  const circle = document.createElementNS(SVG_NS, "circle");
  circle.setAttribute("cx", "11");
  circle.setAttribute("cy", "11");
  circle.setAttribute("r", "7");

  const handle = document.createElementNS(SVG_NS, "line");
  handle.setAttribute("x1", "20");
  handle.setAttribute("y1", "20");
  handle.setAttribute("x2", "16.5");
  handle.setAttribute("y2", "16.5");
  handle.setAttribute("stroke-linecap", "round");

  svg.append(circle, handle);
  return svg;
}
