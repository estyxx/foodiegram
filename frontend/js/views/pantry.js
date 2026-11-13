// @ts-check

import {
  addPantryItem,
  deletePantryItem,
  getPantry,
  updatePantryItem,
} from "../api/client.js";

/** @typedef {import("../api/client.js").PantryItem} PantryItem */

/** Locations in shopping order, with their display label. */
const LOCATIONS = /** @type {const} */ ([
  ["fridge", "Fridge"],
  ["pantry", "Pantry"],
  ["freezer", "Freezer"],
  ["unknown", "Other"],
]);
const SOON_DAYS = 3;
const MS_PER_DAY = 86400000;

/**
 * @param {string} tag
 * @param {string} className
 * @returns {HTMLElement}
 */
function el(tag, className) {
  const node = document.createElement(tag);
  node.className = className;
  return node;
}

/**
 * Whole days from today to an ISO date, or null when there is no date.
 * @param {string | null} expires
 * @returns {number | null}
 */
function daysToExpiry(expires) {
  if (expires === null) {
    return null;
  }
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(`${expires}T00:00:00`);
  return Math.round((due.getTime() - today.getTime()) / MS_PER_DAY);
}

/**
 * Sort key: soonest expiry first, undated last, then by name.
 * @param {PantryItem} item
 * @returns {number}
 */
function expirySort(item) {
  const days = daysToExpiry(item.expires);
  return days === null ? Number.MAX_SAFE_INTEGER : days;
}

/**
 * @param {string | null} expires
 * @returns {HTMLElement | null}
 */
function expiryBadge(expires) {
  const days = daysToExpiry(expires);
  if (days === null || days > SOON_DAYS) {
    return null;
  }
  const badge = el("span", "pantry__badge");
  if (days < 0) {
    badge.classList.add("pantry__badge--expired");
    badge.textContent = "Expired";
  } else {
    badge.classList.add("pantry__badge--soon");
    badge.textContent = days === 0 ? "Today" : `${days}d`;
  }
  return badge;
}

/**
 * A labelled location <select> prefilled to current.
 * @param {string} current
 * @returns {HTMLSelectElement}
 */
function locationSelect(current) {
  const select = document.createElement("select");
  select.className = "pantry__input";
  select.setAttribute("aria-label", "Location");
  for (const [value, label] of LOCATIONS) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    option.selected = value === current;
    select.append(option);
  }
  return select;
}

/**
 * One pantry item: a read row that swaps in place for an editor on "Edit".
 * @param {PantryItem} item
 * @param {() => void} reload
 * @returns {HTMLLIElement}
 */
function renderItem(item, reload) {
  const li = document.createElement("li");
  li.className = "pantry__item";
  showRead();
  return li;

  function showRead() {
    const main = el("div", "pantry__item-main");
    const name = el("span", "pantry__name");
    name.textContent = item.name;
    main.append(name);
    if (item.quantity) {
      const qty = el("span", "pantry__qty");
      qty.textContent = item.quantity;
      main.append(qty);
    }
    const badge = expiryBadge(item.expires);
    if (badge) {
      main.append(badge);
    }

    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "pantry__edit";
    edit.setAttribute("aria-label", `Edit ${item.name}`);
    edit.textContent = "✎";
    edit.addEventListener("click", showEdit);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "pantry__remove";
    remove.setAttribute("aria-label", `Remove ${item.name}`);
    remove.textContent = "×";
    remove.addEventListener("click", () => {
      if (item.id !== null) {
        void deletePantryItem(item.id).then(reload);
      }
    });

    li.replaceChildren(main, edit, remove);
  }

  function showEdit() {
    li.replaceChildren(buildItemEditor(item, showRead, reload));
  }
}

/**
 * Inline editor for a pantry item: name, quantity, location and expiry.
 * @param {PantryItem} item
 * @param {() => void} onCancel
 * @param {() => void} reload
 * @returns {HTMLFormElement}
 */
function buildItemEditor(item, onCancel, reload) {
  const form = document.createElement("form");
  form.className = "pantry__edit-form";

  const name = document.createElement("input");
  name.type = "text";
  name.required = true;
  name.value = item.name;
  name.className = "pantry__input pantry__input--name";
  name.setAttribute("aria-label", "Item name");

  const location = locationSelect(item.location);

  const quantity = document.createElement("input");
  quantity.type = "text";
  quantity.value = item.quantity;
  quantity.placeholder = "Qty (optional)";
  quantity.className = "pantry__input pantry__input--qty";
  quantity.setAttribute("aria-label", "Quantity");

  const expires = document.createElement("input");
  expires.type = "date";
  expires.value = item.expires ?? "";
  expires.className = "pantry__input";
  expires.setAttribute("aria-label", "Expiry date");

  const save = document.createElement("button");
  save.type = "submit";
  save.className = "pantry__add";
  save.textContent = "Save";

  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.className = "pantry__cancel";
  cancel.textContent = "Cancel";
  cancel.addEventListener("click", onCancel);

  form.append(name, location, quantity, expires, save, cancel);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (item.id === null || name.value.trim() === "") {
      return;
    }
    save.disabled = true;
    void updatePantryItem(item.id, {
      name: name.value.trim(),
      location: location.value,
      quantity: quantity.value.trim(),
      expires: expires.value || null,
    })
      .then(reload)
      .catch(() => {
        save.disabled = false;
      });
  });
  return form;
}

/**
 * @param {string} label
 * @param {PantryItem[]} items
 * @param {() => void} reload
 * @returns {HTMLElement}
 */
function renderGroup(label, items, reload) {
  const section = el("section", "pantry__group");
  const heading = el("h2", "pantry__location");
  heading.textContent = `${label} (${items.length})`;
  const list = document.createElement("ul");
  list.className = "pantry__items";
  for (const item of [...items].sort((a, b) => expirySort(a) - expirySort(b))) {
    list.append(renderItem(item, reload));
  }
  section.append(heading, list);
  return section;
}

/**
 * The add-an-item form.
 * @param {() => void} reload
 * @returns {HTMLFormElement}
 */
function renderForm(reload) {
  const form = document.createElement("form");
  form.className = "pantry__form";
  const name = document.createElement("input");
  name.type = "text";
  name.required = true;
  name.placeholder = "Add an item…";
  name.className = "pantry__input pantry__input--name";
  name.setAttribute("aria-label", "Item name");

  const location = locationSelect("fridge");

  const quantity = document.createElement("input");
  quantity.type = "text";
  quantity.placeholder = "Qty (optional)";
  quantity.className = "pantry__input pantry__input--qty";
  quantity.setAttribute("aria-label", "Quantity");

  const expires = document.createElement("input");
  expires.type = "date";
  expires.className = "pantry__input";
  expires.setAttribute("aria-label", "Expiry date");

  const submit = document.createElement("button");
  submit.type = "submit";
  submit.className = "pantry__add";
  submit.textContent = "Add";

  form.append(name, location, quantity, expires, submit);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (name.value.trim() === "") {
      return;
    }
    void addPantryItem({
      name: name.value.trim(),
      kind: "fresh",
      location: location.value,
      quantity: quantity.value.trim(),
      expires: expires.value || null,
    }).then(reload);
  });
  return form;
}

/**
 * Render the pantry page (#pantry).
 * @param {HTMLElement} container
 */
export async function renderPantry(container) {
  const page = el("div", "pantry");
  const title = el("h1", "pantry__title");
  title.textContent = "Pantry";
  const body = el("div", "pantry__body");
  const reload = () => {
    void renderPantry(container);
  };
  page.append(title, renderForm(reload), body);
  container.replaceChildren(page);

  /** @type {PantryItem[]} */
  let items;
  try {
    items = await getPantry();
  } catch {
    body.append(stateMsg("Could not load the pantry."));
    return;
  }

  if (items.length === 0) {
    body.append(stateMsg("The pantry is empty. Add what you keep in stock above."));
    return;
  }

  for (const [location, label] of LOCATIONS) {
    const inLocation = items.filter((item) => item.location === location);
    if (inLocation.length > 0) {
      body.append(renderGroup(label, inLocation, reload));
    }
  }
}

/**
 * @param {string} message
 * @returns {HTMLElement}
 */
function stateMsg(message) {
  const p = el("p", "state-msg");
  p.textContent = message;
  return p;
}
