// @ts-check

import { addPantryItem, deletePantryItem, getPantry } from "../api/client.js";
import { formatDayLabel } from "../lib/format.js";
import { isoDate } from "../lib/week.js";

/** @typedef {import("../api/client.js").PantryItem} PantryItem */
/** @typedef {import("../api/client.js").PantryLocation} PantryLocation */

/** @typedef {"all" | PantryLocation} LocationFilter */

/** D31's places, in the order a kitchen is walked through. */
const LOCATIONS = /** @type {const} */ ([
  ["fridge", "Fridge"],
  ["freezer", "Freezer"],
  ["pantry", "Pantry"],
]);
const UNKNOWN_LABEL = "Not set";
const SOON_DAYS = 2;
const MS_PER_DAY = 86_400_000;

/**
 * Render the pantry view (#pantry): what the kitchen holds, filterable by
 * where it is kept, with add and remove (11.6, D31). Names stay free text.
 * @param {HTMLElement} container
 * @returns {Promise<void>}
 */
export async function renderPantry(container) {
  container.replaceChildren();
  const today = isoDate(new Date());

  /** @type {PantryItem[]} */
  let items = [];
  /** @type {LocationFilter} */
  let filter = "all";

  const header = document.createElement("header");
  header.className = "pantry__header";
  const title = document.createElement("h1");
  title.className = "plan__title";
  title.textContent = "Pantry";
  const summary = document.createElement("p");
  summary.className = "pantry__summary";
  summary.setAttribute("aria-live", "polite");
  header.append(title, summary);

  const filters = document.createElement("div");
  filters.className = "segmented pantry__filters";
  filters.setAttribute("role", "group");
  filters.setAttribute("aria-label", "Show items kept in");

  const error = document.createElement("p");
  error.className = "state-msg state-msg--error";
  error.setAttribute("role", "alert");
  error.hidden = true;

  const list = document.createElement("ul");
  list.className = "pantry__list";

  const empty = document.createElement("p");
  empty.className = "state-msg";

  const form = buildAddForm(async (item) => {
    const saved = await addPantryItem(item);
    items = [...items, saved].sort((a, b) => a.name.localeCompare(b.name));
    showError("");
    render();
  });

  container.append(header, form.element, filters, error, list, empty);

  /**
   * @param {string} message
   */
  function showError(message) {
    error.hidden = message === "";
    error.textContent = message;
  }

  /**
   * @param {PantryItem} item
   */
  async function remove(item) {
    try {
      await deletePantryItem(item.id);
      items = items.filter((existing) => existing.id !== item.id);
      showError("");
      render();
    } catch {
      showError(`Couldn’t remove ${item.name} — try again.`);
    }
  }

  function render() {
    renderFilters();
    const shown =
      filter === "all" ? items : items.filter((item) => item.location === filter);
    const rowOptions = { today, showLocation: filter === "all", onRemove: remove };
    list.replaceChildren(...shown.map((item) => buildRow(item, rowOptions)));
    summary.textContent =
      items.length === 0
        ? "Nothing here yet."
        : `${items.length} ${items.length === 1 ? "item" : "items"} in the kitchen`;
    empty.hidden = shown.length > 0 || items.length === 0;
    empty.textContent = `Nothing in the ${locationLabel(filter).toLowerCase()}.`;
  }

  function renderFilters() {
    const unknown = items.some((item) => item.location === "unknown");
    /** @type {(readonly [LocationFilter, string])[]} */
    const options = [["all", "All"], ...LOCATIONS];
    if (unknown) {
      options.push(["unknown", UNKNOWN_LABEL]);
    }
    if (filter === "unknown" && !unknown) {
      filter = "all";
    }
    filters.replaceChildren(
      ...options.map(([value, label]) => {
        const count =
          value === "all"
            ? items.length
            : items.filter((item) => item.location === value).length;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "segmented__option";
        const active = value === filter;
        button.classList.toggle("segmented__option--active", active);
        button.setAttribute("aria-pressed", String(active));
        button.textContent = `${label} · ${count}`;
        button.addEventListener("click", () => {
          filter = value;
          render();
        });
        return button;
      }),
    );
  }

  try {
    items = await getPantry();
  } catch {
    showError("Couldn’t load the pantry — try again.");
  }
  render();
}

/**
 * @param {LocationFilter} value
 * @returns {string}
 */
function locationLabel(value) {
  const known = LOCATIONS.find(([key]) => key === value);
  if (known) {
    return known[1];
  }
  return value === "unknown" ? UNKNOWN_LABEL : "Kitchen";
}

/**
 * Days from today to an ISO date (negative once past).
 * @param {string} today
 * @param {string} date
 * @returns {number}
 */
function daysUntil(today, date) {
  const start = new Date(`${today}T00:00:00`).getTime();
  const end = new Date(`${date}T00:00:00`).getTime();
  return Math.round((end - start) / MS_PER_DAY);
}

/**
 * @param {PantryItem} item
 * @param {{ today: string, showLocation: boolean, onRemove: (item: PantryItem) => void }} options
 * @returns {HTMLLIElement}
 */
function buildRow(item, options) {
  const row = document.createElement("li");
  row.className = "pantry-item";

  const main = document.createElement("div");
  main.className = "pantry-item__main";
  const name = document.createElement("span");
  name.className = "pantry-item__name";
  name.textContent = item.name;
  main.append(name);
  if (item.quantity !== "") {
    const quantity = document.createElement("span");
    quantity.className = "pantry-item__quantity";
    quantity.textContent = item.quantity;
    main.append(quantity);
  }

  const meta = document.createElement("div");
  meta.className = "pantry-item__meta";
  const tags = [item.kind === "fresh" ? "Fresh" : "Staple"];
  if (options.showLocation) {
    tags.unshift(locationLabel(item.location));
  }
  const tagText = document.createElement("span");
  tagText.textContent = tags.join(" · ");
  meta.append(tagText);
  if (item.expires !== null) {
    meta.append(buildExpiry(item.expires, options.today));
  }

  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "btn-ghost";
  remove.textContent = "Remove";
  remove.setAttribute("aria-label", `Remove ${item.name}`);
  remove.addEventListener("click", () => options.onRemove(item));

  row.append(main, meta, remove);
  return row;
}

/**
 * "expires lun 2 nov", flagged when it is close or past.
 * @param {string} expires
 * @param {string} today
 * @returns {HTMLElement}
 */
function buildExpiry(expires, today) {
  const days = daysUntil(today, expires);
  const el = document.createElement("span");
  el.className = "pantry-item__expiry";
  const date = formatDayLabel(expires);
  if (days < 0) {
    el.classList.add("pantry-item__expiry--past");
    el.textContent = `expired ${date}`;
  } else if (days <= SOON_DAYS) {
    el.classList.add("pantry-item__expiry--soon");
    el.textContent = days === 0 ? "expires today" : `expires ${date}`;
  } else {
    el.textContent = `expires ${date}`;
  }
  return el;
}

/**
 * @typedef {object} AddFormView
 * @property {HTMLFormElement} element
 */

/**
 * The add-item form. Only the name is required; location defaults to the
 * fridge and kind to fresh, the common case for a quick add.
 * @param {(item: import("../api/client.js").PantryItemCreate) => Promise<void>} onAdd
 * @returns {AddFormView}
 */
function buildAddForm(onAdd) {
  const form = document.createElement("form");
  form.className = "pantry-add";
  form.noValidate = true;
  form.setAttribute("aria-label", "Add to the pantry");

  const name = labelled("Item", input("text"));
  name.control.placeholder = "e.g. ceci cotti";
  const quantity = labelled("Quantity (optional)", input("text"));
  quantity.control.placeholder = "e.g. mezzo barattolo";
  const location = labelled(
    "Kept in",
    select(LOCATIONS.map(([value, label]) => [value, label])),
  );
  const kind = labelled("Kind", select([["fresh", "Fresh"], ["staple", "Staple"]]));
  const expires = labelled("Expires (optional)", input("date"));

  const error = document.createElement("p");
  error.className = "state-msg state-msg--error pantry-add__error";
  error.setAttribute("role", "alert");
  error.hidden = true;

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "btn btn--primary pantry-add__submit";
  submit.textContent = "Add";

  form.append(
    name.element,
    quantity.element,
    location.element,
    kind.element,
    expires.element,
    submit,
    error,
  );

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const itemName = name.control.value.trim();
    if (itemName === "") {
      error.hidden = false;
      error.textContent = "Name the item.";
      name.control.focus();
      return;
    }
    submit.disabled = true;
    try {
      await onAdd({
        name: itemName,
        kind: kind.control.value === "staple" ? "staple" : "fresh",
        location: /** @type {PantryLocation} */ (location.control.value),
        quantity: quantity.control.value.trim(),
        expires: expires.control.value || null,
      });
      error.hidden = true;
      name.control.value = "";
      quantity.control.value = "";
      expires.control.value = "";
      name.control.focus();
    } catch {
      error.hidden = false;
      error.textContent = "Couldn’t add it — try again.";
    } finally {
      submit.disabled = false;
    }
  });
  return { element: form };
}

/**
 * @param {string} type
 * @returns {HTMLInputElement}
 */
function input(type) {
  const el = document.createElement("input");
  el.type = type;
  return el;
}

/**
 * @param {readonly (readonly [string, string])[]} options
 * @returns {HTMLSelectElement}
 */
function select(options) {
  const el = document.createElement("select");
  for (const [value, label] of options) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    el.append(option);
  }
  return el;
}

let fieldIds = 0;

/**
 * A control with a label tied by for/id. Not wrapped: a label around a
 * <select> folds the option texts into its accessible name.
 * @template {HTMLInputElement | HTMLSelectElement} C
 * @param {string} label
 * @param {C} control
 * @returns {{ element: HTMLDivElement, control: C }}
 */
function labelled(label, control) {
  const wrap = document.createElement("div");
  wrap.className = "pantry-add__field";
  fieldIds += 1;
  control.id = `pantry-add-${fieldIds}`;
  control.classList.add("pantry-add__control");
  const text = document.createElement("label");
  text.className = "pantry-add__label";
  text.htmlFor = control.id;
  text.textContent = label;
  wrap.append(text, control);
  return { element: wrap, control };
}
