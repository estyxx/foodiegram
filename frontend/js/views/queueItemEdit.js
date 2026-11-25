// @ts-check

import { pasteCaption, reextractQueued } from "../api/client.js";

/** @typedef {import("../api/client.js").PendingLink} PendingLink */

const SNIPPET_CHARS = 160;

/**
 * @param {string} tag
 * @param {string} className
 * @param {string} [text]
 * @returns {HTMLElement}
 */
function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) {
    node.textContent = text;
  }
  return node;
}

/**
 * @param {string} label
 * @param {string} className
 * @returns {HTMLButtonElement}
 */
function button(label, className) {
  const btn = /** @type {HTMLButtonElement} */ (el("button", className, label));
  btn.type = "button";
  return btn;
}

/**
 * The body of a link that has a caption: a snippet, a link to the recipe once
 * imported, and an editor to change the text (the caption, or your own notes
 * when the recipe is in the comments or on a website) and extract it again now.
 * @param {PendingLink} link
 * @param {(notice?: string) => void} reload
 * @returns {HTMLElement}
 */
export function captionedBody(link, reload) {
  const body = el("div", "queue__captioned");
  const caption = link.caption ?? "";
  const snippet = el(
    "p",
    "queue__snippet",
    caption.length > SNIPPET_CHARS ? `${caption.slice(0, SNIPPET_CHARS)}…` : caption,
  );
  body.append(snippet);

  const row = el("div", "queue__caption-actions");
  if (link.status === "imported") {
    const recipe = /** @type {HTMLAnchorElement} */ (el("a", "queue__open", "Open recipe"));
    recipe.href = `#recipe/${encodeURIComponent(link.code)}`;
    row.append(recipe);
  }
  // A link inside a running batch waits for the batch, so it is not editable.
  if (link.status !== "extracting") {
    const edit = button("Edit text", "queue__find");
    edit.setAttribute("aria-expanded", "false");
    row.append(edit);
    edit.addEventListener("click", () => {
      edit.setAttribute("aria-expanded", "true");
      row.hidden = true;
      body.append(editor(link, reload));
    });
  }
  body.append(row);
  return body;
}

/**
 * @param {PendingLink} link
 * @param {(notice?: string) => void} reload
 * @returns {HTMLElement}
 */
function editor(link, reload) {
  const form = el("form", "queue__caption-form");
  const area = /** @type {HTMLTextAreaElement} */ (el("textarea", "queue__caption-input"));
  area.rows = 6;
  area.value = link.caption ?? "";
  area.setAttribute("aria-label", `Text to extract ${link.code} from`);
  const hint = el(
    "p",
    "queue__hint",
    "Change the caption or add your notes, for example the ingredients from the comments.",
  );
  const status = el("p", "queue__hint");
  status.setAttribute("role", "status");

  const extract = button(
    link.status === "imported" ? "Re-extract now" : "Extract now",
    "queue__save",
  );
  const save = button("Save only", "queue__find");
  const cancel = button("Cancel", "queue__find");
  const actions = el("div", "queue__caption-actions");
  actions.append(extract, save, cancel);
  form.append(hint, area, actions, status);

  /** @param {boolean} busy */
  const setBusy = (busy) => {
    for (const control of [extract, save, cancel]) {
      control.disabled = busy;
    }
    area.readOnly = busy;
  };

  extract.addEventListener("click", () => {
    const text = area.value.trim();
    if (text === "") {
      status.textContent = "Write something to extract from first.";
      return;
    }
    setBusy(true);
    status.textContent = "Extracting… this takes a few seconds.";
    reextractQueued(link.code, text)
      .then(() => reload(`Extracted ${link.code}. Open the recipe to check it.`))
      .catch(() => {
        setBusy(false);
        status.textContent = "The extraction did not come back. Try again in a moment.";
      });
  });
  save.addEventListener("click", () => {
    const text = area.value.trim();
    if (text === "") {
      return;
    }
    setBusy(true);
    void pasteCaption(link.code, text).then(() => reload("Saved."));
  });
  cancel.addEventListener("click", () => reload());
  return form;
}
