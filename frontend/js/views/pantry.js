// @ts-check

import {
  addPantryItem,
  deletePantryItem,
  getPantry,
  updatePantryItem,
} from "../api/client.js";
import {
  LOCATIONS,
  expiryNote,
  expiryStatus,
  isoOffset,
  locationLabel,
  sections,
  summaryLine,
  useSoon,
} from "../lib/pantryModel.js";

/** @typedef {import("../api/client.js").PantryItem} PantryItem */

const TOAST_MS = 7000;
const STAPLES = ["olio extravergine", "sale", "pasta", "ceci secchi", "passata di pomodoro"];
const QUICK_DATES = /** @type {const} */ ([
  ["No date", null],
  ["+3 days", 3],
  ["+1 week", 7],
  ["+1 month", 30],
]);

/**
 * @param {string} tag
 * @param {string} className
 * @param {string} [text]
 * @returns {HTMLElement}
 */
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) {
    node.className = className;
  }
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/**
 * A down chevron, decorative.
 * @returns {SVGElement}
 */
function chevron() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 14 14");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", "pantry__chevron");
  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", "M3.5 5.5L7 9l3.5-3.5");
  svg.append(path);
  return svg;
}

/**
 * A four-way segmented location picker. Returns the fieldset plus a getter.
 * @param {string} legend
 * @param {string} current
 * @param {(value: string) => void} onPick
 * @returns {HTMLFieldSetElement}
 */
function segmentedLocation(legend, current, onPick) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "pantry__seg-set";
  const caption = el("legend", "pantry__field-label", legend);
  const group = el("div", "pantry__seg");
  const name = `loc-${Math.random().toString(36).slice(2, 8)}`;
  for (const [value, label] of LOCATIONS) {
    const option = document.createElement("label");
    option.className = "pantry__seg-btn";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = name;
    radio.value = value;
    radio.checked = value === current;
    radio.className = "pantry__seg-radio";
    radio.addEventListener("change", () => onPick(value));
    option.append(radio, document.createTextNode(label));
    group.append(option);
  }
  fieldset.append(caption, group);
  return fieldset;
}

/**
 * A labelled text/date input inside its own field wrapper.
 * @param {string} label
 * @param {string} type
 * @param {string} value
 * @param {string} [placeholder]
 * @returns {{ field: HTMLElement, input: HTMLInputElement }}
 */
function field(label, type, value, placeholder) {
  const wrapper = el("label", "pantry__field");
  wrapper.append(el("span", "pantry__field-label", label));
  const input = document.createElement("input");
  input.type = type;
  input.value = value;
  input.className = "pantry__input";
  if (placeholder) {
    input.placeholder = placeholder;
  }
  wrapper.append(input);
  return { field: wrapper, input };
}

/**
 * Render the pantry page (#pantry) with its own local state.
 * @param {HTMLElement} container
 */
export async function renderPantry(container) {
  const today = new Date();

  /**
   * @typedef {object} Toast
   * @property {string} message
   * @property {(() => void) | null} undo
   */

  const state = {
    /** @type {PantryItem[]} */
    items: [],
    /** @type {number | null} */
    editId: null,
    /** @type {{ name: string, location: string, quantity: string, expires: string }} */
    editDraft: { name: "", location: "fridge", quantity: "", expires: "" },
    /** @type {{ name: string, location: string, quantity: string, expires: string }} */
    addDraft: { name: "", location: "fridge", quantity: "", expires: "" },
    addOpen: false,
    expOpen: false,
    /** @type {number | null} */
    flashId: null,
    /** @type {Toast | null} */
    toast: null,
  };
  /** @type {ReturnType<typeof setTimeout> | undefined} */
  let toastTimer;

  try {
    state.items = await getPantry();
  } catch {
    container.replaceChildren(stateMsg("Could not load the pantry."));
    return;
  }

  /**
   * @param {string} message
   * @param {(() => void) | null} undo
   */
  function showToast(message, undo) {
    state.toast = { message, undo };
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      state.toast = null;
      state.flashId = null;
      paint();
    }, TOAST_MS);
  }

  /** Reload from the server after an unexpected write failure. */
  async function resync() {
    try {
      state.items = await getPantry();
    } catch {
      // Keep the optimistic view; a later action will retry.
    }
    paint();
  }

  /**
   * @param {PantryItem} item
   */
  function openEditor(item) {
    if (item.id === null) {
      return;
    }
    state.editId = item.id;
    state.editDraft = {
      name: item.name,
      location: item.location,
      quantity: item.quantity,
      expires: item.expires ?? "",
    };
    paint();
  }

  function closeEditor() {
    state.editId = null;
    paint();
  }

  /**
   * @param {PantryItem} item
   */
  function saveEditor(item) {
    if (item.id === null) {
      return;
    }
    const id = item.id;
    const next = state.editDraft;
    const name = next.name.trim();
    if (name === "") {
      return;
    }
    const moved = next.location !== item.location;
    const updated = {
      ...item,
      name,
      location: next.location,
      quantity: next.quantity.trim(),
      expires: next.expires || null,
    };
    state.items = state.items.map((row) => (row.id === id ? updated : row));
    state.editId = null;
    state.flashId = id;
    const message = moved ? `${name} moved to ${locationLabel(next.location)}.` : `${name} saved.`;
    showToast(
      message,
      moved
        ? () => {
            state.items = state.items.map((row) =>
              row.id === id ? { ...row, location: item.location } : row,
            );
            state.flashId = id;
            state.toast = null;
            paint();
            void updatePantryItem(id, { location: item.location }).catch(resync);
          }
        : null,
    );
    paint();
    void updatePantryItem(id, {
      name,
      location: next.location,
      quantity: next.quantity.trim(),
      expires: next.expires || null,
    }).catch(resync);
  }

  /**
   * @param {PantryItem} item
   */
  function removeItem(item) {
    if (item.id === null) {
      return;
    }
    const id = item.id;
    const snapshot = item;
    state.items = state.items.filter((row) => row.id !== id);
    state.editId = null;
    showToast(`${item.name} removed.`, () => {
      state.toast = null;
      void addPantryItem({
        name: snapshot.name,
        kind: snapshot.kind,
        location: snapshot.location,
        quantity: snapshot.quantity,
        expires: snapshot.expires,
      })
        .then((created) => {
          state.items = [...state.items, created];
          state.flashId = created.id;
          paint();
        })
        .catch(resync);
    });
    paint();
    void deletePantryItem(id).catch(resync);
  }

  /**
   * @param {{ name: string, location: string, quantity: string, expires: string }} draft
   */
  function addDraft(draft) {
    const name = draft.name.trim();
    if (name === "") {
      return;
    }
    state.addDraft = { name: "", location: draft.location, quantity: "", expires: "" };
    void addPantryItem({
      name,
      kind: "fresh",
      location: draft.location,
      quantity: draft.quantity.trim(),
      expires: draft.expires || null,
    })
      .then((created) => {
        state.items = [...state.items, created];
        state.flashId = created.id;
        showToast(`${name} added to ${locationLabel(draft.location)}.`, () => {
          state.toast = null;
          if (created.id !== null) {
            const id = created.id;
            state.items = state.items.filter((row) => row.id !== id);
            paint();
            void deletePantryItem(id).catch(resync);
          }
        });
        paint();
      })
      .catch(resync);
  }

  // ---- rendering ----------------------------------------------------------

  /**
   * @param {PantryItem} item
   * @returns {HTMLLIElement}
   */
  function renderRow(item) {
    const li = document.createElement("li");
    li.className = "pantry__item";
    if (state.flashId !== null && item.id === state.flashId) {
      li.classList.add("pantry__item--flash");
    }
    if (state.editId !== null && item.id === state.editId) {
      li.append(renderEditor(item));
    } else {
      li.append(renderReadRow(item));
    }
    return li;
  }

  /**
   * @param {PantryItem} item
   * @returns {HTMLButtonElement}
   */
  function renderReadRow(item) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "pantry__row";
    button.addEventListener("click", () => openEditor(item));

    const main = el("div", "pantry__row-main");
    main.append(el("span", "pantry__name", item.name));
    if (item.quantity) {
      main.append(el("span", "pantry__qty", item.quantity));
    }
    button.append(main);

    const status = expiryStatus(item.expires, today);
    if (status) {
      const badge = el("span", "pantry__badge", status.short);
      badge.classList.add(
        status.kind === "expired" ? "pantry__badge--expired" : "pantry__badge--soon",
      );
      button.append(badge);
    }
    button.append(chevron());
    return button;
  }

  /**
   * @param {PantryItem} item
   * @returns {HTMLFormElement}
   */
  function renderEditor(item) {
    const form = document.createElement("form");
    form.className = "pantry__editor";
    form.setAttribute("aria-label", `Edit ${item.name}`);
    const draft = state.editDraft;

    const head = el("div", "pantry__editor-head");
    head.append(el("span", "pantry__eyebrow", "Editing"));
    const close = el("button", "pantry__icon-btn");
    close.setAttribute("type", "button");
    close.setAttribute("aria-label", "Close without saving");
    close.textContent = "×";
    close.addEventListener("click", closeEditor);
    head.append(close);
    form.append(head);

    const name = field("Name", "text", draft.name);
    name.input.required = true;
    name.input.addEventListener("input", () => {
      draft.name = name.input.value;
    });
    const quantity = field("Quantity", "text", draft.quantity, "optional, e.g. mezzo barattolo");
    quantity.input.addEventListener("input", () => {
      draft.quantity = quantity.input.value;
    });
    form.append(name.field, quantity.field);

    const movedNote = el("p", "pantry__moved-note");
    const refreshMovedNote = () => {
      if (draft.location !== item.location) {
        movedNote.textContent = `Moves from ${locationLabel(item.location)} to ${locationLabel(draft.location)} when you save.`;
        movedNote.hidden = false;
      } else {
        movedNote.hidden = true;
      }
      save.textContent = draft.location !== item.location ? "Save & move" : "Save";
    };
    const seg = segmentedLocation("Where it lives", draft.location, (value) => {
      draft.location = value;
      refreshMovedNote();
    });
    seg.append(movedNote);
    form.append(seg);

    const expires = field("Best before", "date", draft.expires);
    const noteLine = el("p", "pantry__exp-note");
    const refreshExpNote = () => {
      const status = expiryStatus(draft.expires || null, today);
      noteLine.className = "pantry__exp-note";
      if (status?.kind === "expired") {
        noteLine.classList.add("pantry__exp-note--expired");
      } else if (status?.kind === "soon") {
        noteLine.classList.add("pantry__exp-note--soon");
      }
      noteLine.textContent = expiryNote(draft.expires || null, today);
    };
    expires.input.addEventListener("input", () => {
      draft.expires = expires.input.value;
      refreshExpNote();
    });
    const quick = el("div", "pantry__quick");
    quick.setAttribute("role", "group");
    quick.setAttribute("aria-label", "Quick dates");
    for (const [label, offset] of QUICK_DATES) {
      const chip = el("button", "pantry__chip", label);
      chip.setAttribute("type", "button");
      chip.addEventListener("click", () => {
        draft.expires = offset === null ? "" : isoOffset(today, offset);
        expires.input.value = draft.expires;
        refreshExpNote();
      });
      quick.append(chip);
    }
    const dateBlock = el("div", "pantry__date-block");
    dateBlock.append(expires.field, quick, noteLine);
    form.append(dateBlock);

    const actions = el("div", "pantry__editor-actions");
    const remove = el("button", "pantry__remove", "Remove");
    remove.setAttribute("type", "button");
    remove.addEventListener("click", () => removeItem(item));
    const cancel = el("button", "pantry__cancel", "Cancel");
    cancel.setAttribute("type", "button");
    cancel.addEventListener("click", closeEditor);
    const save = el("button", "pantry__save", "Save");
    save.setAttribute("type", "submit");
    actions.append(remove, cancel, save);
    form.append(actions);

    refreshMovedNote();
    refreshExpNote();

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      saveEditor(item);
    });
    return form;
  }

  /**
   * @param {"desktop" | "mobile"} variant
   * @returns {HTMLFormElement}
   */
  function renderAddForm(variant) {
    const draft = state.addDraft;
    const form = document.createElement("form");
    form.className = `pantry__add-form pantry__add-form--${variant}`;
    if (variant === "mobile" && state.addOpen) {
      form.classList.add("pantry__add-form--open");
    }
    form.setAttribute("aria-label", "Add an item");

    const details = el("div", "pantry__add-details");
    if (variant === "desktop") {
      details.append(el("div", "pantry__eyebrow", "Add an item"));
    }

    const submit = el("button", "pantry__save", variant === "desktop" ? "" : "Add");
    submit.setAttribute("type", "submit");
    const seg = segmentedLocation("Where", draft.location, (value) => {
      draft.location = value;
      if (variant === "desktop") {
        submit.textContent = `Add to ${locationLabel(value)}`;
      }
    });

    const row = el("div", "pantry__add-row");
    const quantity = field("Quantity", "text", draft.quantity, "optional");
    quantity.input.addEventListener("input", () => {
      draft.quantity = quantity.input.value;
    });
    const expires = field("Best before", "date", draft.expires);
    expires.input.addEventListener("input", () => {
      draft.expires = expires.input.value;
    });
    row.append(quantity.field, expires.field);

    if (variant === "desktop") {
      const nameField = field("Name", "text", draft.name, "e.g. ceci secchi");
      nameField.input.required = true;
      nameField.input.addEventListener("input", () => {
        draft.name = nameField.input.value;
      });
      submit.classList.add("pantry__save--block");
      submit.textContent = `Add to ${locationLabel(draft.location)}`;
      details.append(nameField.field, seg, row, submit);
      form.append(details);
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        draft.name = nameField.input.value;
        addDraft(draft);
      });
      return form;
    }

    // mobile: collapsible details above a name + add bar
    details.append(seg, row);
    const bar = el("div", "pantry__add-bar");
    const nameWrap = el("label", "pantry__add-name");
    nameWrap.append(el("span", "pantry__vh", "Add an item"));
    const nameInput = document.createElement("input");
    nameInput.type = "text";
    nameInput.value = draft.name;
    nameInput.placeholder = "Add an item…";
    nameInput.className = "pantry__input";
    nameInput.addEventListener("input", () => {
      draft.name = nameInput.value;
    });
    nameInput.addEventListener("focus", () => {
      if (!state.addOpen) {
        state.addOpen = true;
        form.classList.add("pantry__add-form--open");
      }
    });
    nameWrap.append(nameInput);
    bar.append(nameWrap, submit);
    form.append(details, bar);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      draft.name = nameInput.value;
      addDraft(draft);
    });
    return form;
  }

  /**
   * @param {PantryItem[]} list
   * @param {boolean} expired
   * @returns {HTMLUListElement}
   */
  function renderUseList(list, expired) {
    const ul = document.createElement("ul");
    ul.className = "pantry__use-list";
    for (const item of list) {
      const status = expiryStatus(item.expires, today);
      const li = document.createElement("li");
      li.className = "pantry__use-item";
      const button = el("button", "pantry__use-row");
      button.setAttribute("type", "button");
      button.addEventListener("click", () => openEditor(item));
      button.append(el("span", "pantry__use-name", item.name));
      button.append(el("span", "pantry__use-loc", locationLabel(item.location)));
      const when = el("span", "pantry__use-when", status ? status.long : "");
      if (expired) {
        when.classList.add("pantry__use-when--expired");
      }
      button.append(when);
      li.append(button);
      ul.append(li);
    }
    return ul;
  }

  /**
   * @returns {HTMLElement | null}
   */
  function renderUseSoon() {
    const { soon, expired } = useSoon(state.items, today);
    if (soon.length === 0 && expired.length === 0) {
      return null;
    }
    const section = el("section", "pantry__soon");
    section.setAttribute("aria-label", "Use soon");
    const head = el("div", "pantry__soon-head");
    head.append(el("h2", "pantry__soon-title", "Use soon"));
    head.append(
      el("span", "pantry__eyebrow", soon.length ? `${soon.length} this week` : "nothing pressing"),
    );
    section.append(head);
    if (soon.length) {
      section.append(renderUseList(soon, false));
    }
    if (expired.length) {
      const toggle = el("button", "pantry__exp-toggle");
      toggle.setAttribute("type", "button");
      toggle.setAttribute("aria-expanded", state.expOpen ? "true" : "false");
      const label = `${expired.length} ${expired.length === 1 ? "item is" : "items are"} past the date`;
      toggle.append(el("span", "pantry__exp-toggle-label", label));
      toggle.append(el("span", "pantry__eyebrow", state.expOpen ? "Hide" : "Show"));
      toggle.addEventListener("click", () => {
        state.expOpen = !state.expOpen;
        paint();
      });
      section.append(toggle);
      if (state.expOpen) {
        section.append(renderUseList(expired, true));
      }
    }
    return section;
  }

  /**
   * @returns {HTMLElement}
   */
  function renderEmpty() {
    const section = el("section", "pantry__empty");
    section.setAttribute("aria-label", "Empty pantry");
    section.append(el("div", "pantry__eyebrow", "Nothing stored yet"));
    section.append(
      el("h2", "pantry__empty-title", "An empty shelf is a fine place to start."),
    );
    section.append(
      el(
        "p",
        "pantry__empty-body",
        "Add what is already in your kitchen. Dispensa will then show what you are missing for a recipe and build the shopping list around it.",
      ),
    );
    const chips = el("div", "pantry__staples");
    for (const name of STAPLES) {
      const chip = el("button", "pantry__chip pantry__chip--staple", `+ ${name}`);
      chip.setAttribute("type", "button");
      chip.addEventListener("click", () =>
        addDraft({ name, location: "pantry", quantity: "", expires: "" }),
      );
      chips.append(chip);
    }
    section.append(chips);
    return section;
  }

  /**
   * @returns {HTMLElement}
   */
  function renderList() {
    const column = el("div", "pantry__list");
    const grouped = sections(state.items, today);

    const chips = el("nav", "pantry__jump");
    chips.setAttribute("aria-label", "Jump to section");
    for (const section of grouped) {
      const chip = el("button", "pantry__jump-chip");
      chip.setAttribute("type", "button");
      chip.append(document.createTextNode(section.label));
      chip.append(el("span", "pantry__jump-count", String(section.items.length)));
      chip.addEventListener("click", () => {
        const target = column.querySelector(`[data-sec="${section.key}"]`);
        target?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      chips.append(chip);
    }
    column.append(chips);

    for (const section of grouped) {
      const block = el("section", "pantry__group");
      block.setAttribute("data-sec", section.key);
      block.setAttribute("aria-label", `${section.label}, ${section.items.length} items`);
      const head = el("div", "pantry__group-head");
      head.append(el("h2", "pantry__group-title", section.label));
      head.append(
        el(
          "span",
          "pantry__eyebrow",
          `${section.items.length} ${section.items.length === 1 ? "item" : "items"}`,
        ),
      );
      if (section.soonCount > 0) {
        head.append(el("span", "pantry__group-note", `${section.soonCount} to use soon`));
      }
      block.append(head);
      const card = el("div", "pantry__card");
      const list = el("ul", "pantry__items");
      for (const item of section.items) {
        list.append(renderRow(item));
      }
      card.append(list);
      block.append(card);
      column.append(block);
    }
    return column;
  }

  function paint() {
    const page = el("div", "pantry");

    const rail = el("div", "pantry__rail");
    const intro = el("div", "pantry__intro");
    intro.append(el("h1", "pantry__title", "Pantry"));
    intro.append(el("p", "pantry__summary", summaryLine(state.items, today)));
    rail.append(intro);
    rail.append(renderAddForm("desktop"));
    const soon = state.items.length > 0 ? renderUseSoon() : null;
    if (soon) {
      rail.append(soon);
    }

    const main = el("div", "pantry__main");
    main.append(rail);
    main.append(state.items.length === 0 ? renderEmpty() : renderList());
    page.append(main);

    if (state.toast) {
      const toast = el("div", "pantry__toast");
      toast.setAttribute("role", "status");
      toast.append(el("span", "pantry__toast-msg", state.toast.message));
      if (state.toast.undo) {
        const undo = el("button", "pantry__toast-undo", "Undo");
        undo.setAttribute("type", "button");
        const action = state.toast.undo;
        undo.addEventListener("click", () => {
          clearTimeout(toastTimer);
          action();
        });
        toast.append(undo);
      }
      page.append(toast);
    }

    page.append(renderAddForm("mobile"));
    container.replaceChildren(page);
  }

  paint();
}

/**
 * @param {string} message
 * @returns {HTMLElement}
 */
function stateMsg(message) {
  return el("p", "state-msg", message);
}
