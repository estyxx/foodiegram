// @ts-check

import { getShoppingList } from "../api/client.js";

/** @typedef {import("../api/client.js").AisleGroup} AisleGroup */
/** @typedef {import("../api/client.js").ShoppingItem} ShoppingItem */

const TICK_KEY_PREFIX = "dispensa.shop.ticked.";
const COPIED_MS = 1500;

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
 * @param {string} message
 * @returns {HTMLElement}
 */
function stateMsg(message) {
  const p = el("p", "state-msg");
  p.textContent = message;
  return p;
}

/**
 * @param {string} weekStart
 * @returns {Set<string>}
 */
function loadTicked(weekStart) {
  try {
    const raw = window.localStorage.getItem(TICK_KEY_PREFIX + weekStart);
    return new Set(raw ? JSON.parse(raw) : []);
  } catch {
    return new Set();
  }
}

/**
 * @param {string} weekStart
 * @param {Set<string>} ticked
 */
function saveTicked(weekStart, ticked) {
  try {
    window.localStorage.setItem(TICK_KEY_PREFIX + weekStart, JSON.stringify([...ticked]));
  } catch {
    // A private window or blocked storage: ticking just will not persist.
  }
}

/**
 * @param {ShoppingItem} item
 * @param {Set<string>} ticked
 * @param {string} weekStart
 * @returns {HTMLLIElement}
 */
function renderItem(item, ticked, weekStart) {
  const li = document.createElement("li");
  li.className = "shop__item";
  const label = el("label", "shop__check");
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = ticked.has(item.name);
  const name = el("span", "shop__name");
  name.textContent = item.name;
  label.append(box, name);
  li.append(label);
  if (item.raw_lines.length > 0) {
    const raw = el("p", "shop__raw");
    raw.textContent = item.raw_lines.join(" · ");
    li.append(raw);
  }
  li.classList.toggle("shop__item--done", box.checked);
  box.addEventListener("change", () => {
    li.classList.toggle("shop__item--done", box.checked);
    if (box.checked) {
      ticked.add(item.name);
    } else {
      ticked.delete(item.name);
    }
    saveTicked(weekStart, ticked);
  });
  return li;
}

/**
 * @param {AisleGroup} group
 * @param {Set<string>} ticked
 * @param {string} weekStart
 * @returns {HTMLElement}
 */
function renderGroup(group, ticked, weekStart) {
  const section = el("section", "shop__group");
  const heading = el("h2", "shop__aisle");
  heading.textContent = group.aisle;
  const list = document.createElement("ul");
  list.className = "shop__items";
  for (const item of group.items) {
    list.append(renderItem(item, ticked, weekStart));
  }
  section.append(heading, list);
  return section;
}

/**
 * @param {AisleGroup[]} groups
 * @returns {string}
 */
function asText(groups) {
  return groups
    .map(
      (group) =>
        `${group.aisle}\n` + group.items.map((item) => `- ${item.name}`).join("\n"),
    )
    .join("\n\n");
}

/**
 * Render the shopping list for a week (#shop/{weekStart}).
 * @param {HTMLElement} container
 * @param {string} weekStart
 */
export async function renderShop(container, weekStart) {
  const ticked = loadTicked(weekStart);

  const page = el("div", "shop");
  const header = el("div", "shop__header");
  const back = document.createElement("a");
  back.className = "shop__back";
  back.href = "#plan";
  back.textContent = "‹ Plan";
  const title = el("h1", "shop__title");
  title.textContent = "Shopping list";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "shop__copy";
  copy.textContent = "Copy list";
  header.append(back, title, copy);

  const body = el("div", "shop__body");
  page.append(header, body);
  container.replaceChildren(page);

  /** @type {AisleGroup[]} */
  let groups;
  try {
    groups = await getShoppingList(weekStart);
  } catch {
    copy.disabled = true;
    body.append(stateMsg("Could not load the shopping list."));
    return;
  }

  const total = groups.reduce((sum, group) => sum + group.items.length, 0);
  if (total === 0) {
    copy.disabled = true;
    body.append(stateMsg("Nothing to buy — plan some meals, or the pantry covers it."));
    return;
  }

  for (const group of groups) {
    body.append(renderGroup(group, ticked, weekStart));
  }

  copy.addEventListener("click", () => {
    void navigator.clipboard?.writeText(asText(groups));
    copy.textContent = "Copied";
    window.setTimeout(() => {
      copy.textContent = "Copy list";
    }, COPIED_MS);
  });
}
