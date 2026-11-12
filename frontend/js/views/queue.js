// @ts-check

import {
  deleteQueued,
  extractQueue,
  getQueue,
  importQueue,
  pasteCaption,
  queueLink,
} from "../api/client.js";

/** @typedef {import("../api/client.js").PendingLink} PendingLink */

const STATUS_LABEL = /** @type {Record<string, string>} */ ({
  new: "Needs caption",
  ready: "Ready",
  extracting: "Extracting…",
  imported: "Imported",
  failed: "Failed",
});

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
 * @param {PendingLink} link
 * @param {() => void} reload
 * @returns {HTMLElement}
 */
function renderItem(link, reload) {
  const item = el("article", "queue__item");

  const head = el("div", "queue__head");
  const open = document.createElement("a");
  open.className = "queue__link";
  open.href = link.url;
  open.target = "_blank";
  open.rel = "noreferrer";
  open.textContent = link.code;
  const status = el("span", `queue__status queue__status--${link.status}`);
  status.textContent = STATUS_LABEL[link.status] ?? link.status;
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "queue__remove";
  remove.setAttribute("aria-label", `Remove ${link.code}`);
  remove.textContent = "×";
  remove.addEventListener("click", () => {
    void deleteQueued(link.code).then(reload);
  });
  head.append(open, status, remove);
  item.append(head);

  if (link.caption === null) {
    const form = document.createElement("form");
    form.className = "queue__caption-form";
    const area = document.createElement("textarea");
    area.className = "queue__caption-input";
    area.rows = 3;
    area.placeholder = "Paste the full caption from Instagram…";
    area.setAttribute("aria-label", `Caption for ${link.code}`);
    const save = document.createElement("button");
    save.type = "submit";
    save.className = "queue__save";
    save.textContent = "Save caption";
    form.append(area, save);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (area.value.trim() === "") {
        return;
      }
      void pasteCaption(link.code, area.value.trim()).then(reload);
    });
    item.append(form);
  } else {
    const snippet = el("p", "queue__snippet");
    snippet.textContent =
      link.caption.length > 160 ? `${link.caption.slice(0, 160)}…` : link.caption;
    item.append(snippet);
  }
  return item;
}

/**
 * The launch/import toolbar: one batch button per actionable queue state.
 * @param {PendingLink[]} links
 * @param {() => void} reload
 * @returns {HTMLElement}
 */
function buildToolbar(links, reload) {
  const ready = links.filter((link) => link.status === "ready").length;
  const extracting = links.filter((link) => link.status === "extracting").length;

  const bar = el("div", "queue__toolbar");
  const status = el("p", "queue__toolbar-status");
  status.setAttribute("role", "status");
  status.setAttribute("aria-live", "polite");

  /**
   * @param {string} label
   * @param {number} n
   * @param {() => Promise<number>} action
   * @param {(n: number) => string} done
   * @returns {HTMLButtonElement}
   */
  const button = (label, n, action, done) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "queue__batch-btn";
    btn.textContent = n > 0 ? `${label} (${n})` : label;
    btn.disabled = n === 0;
    btn.addEventListener("click", () => {
      btn.disabled = true;
      status.textContent = "Working…";
      action()
        .then((count) => {
          status.textContent = done(count);
          reload();
        })
        .catch(() => {
          status.textContent = "That didn't work — check the server and try again.";
          btn.disabled = false;
        });
    });
    return btn;
  };

  bar.append(
    button(
      "Launch extraction",
      ready,
      extractQueue,
      (n) => `Submitted ${n} for extraction.`,
    ),
    button(
      "Import finished",
      extracting,
      importQueue,
      (n) => (n > 0 ? `Imported ${n} recipe${n === 1 ? "" : "s"}.` : "Nothing ready yet."),
    ),
    status,
  );
  return bar;
}

/**
 * Render the capture queue (#queue).
 * @param {HTMLElement} container
 */
export async function renderQueue(container) {
  const page = el("div", "queue");
  const title = el("h1", "queue__title");
  title.textContent = "Queue";

  const addForm = document.createElement("form");
  addForm.className = "queue__add";
  const url = document.createElement("input");
  url.type = "url";
  url.required = true;
  url.placeholder = "Paste an Instagram link…";
  url.className = "queue__add-input";
  url.setAttribute("aria-label", "Instagram link");
  const add = document.createElement("button");
  add.type = "submit";
  add.className = "queue__add-btn";
  add.textContent = "Add";
  addForm.append(url, add);

  const body = el("div", "queue__body");
  const reload = () => {
    void renderQueue(container);
  };
  addForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (url.value.trim() === "") {
      return;
    }
    void queueLink(url.value.trim())
      .then(reload)
      .catch(() => {
        url.setCustomValidity("Already in the library, or not a post link.");
        url.reportValidity();
      });
  });

  page.append(title, addForm, body);
  container.replaceChildren(page);

  /** @type {PendingLink[]} */
  let links;
  try {
    links = await getQueue();
  } catch {
    body.append(stateMsg("Could not load the queue."));
    return;
  }

  if (links.length === 0) {
    body.append(
      stateMsg("Nothing queued. Share an Instagram link here, then paste its caption."),
    );
    return;
  }

  body.append(buildToolbar(links, reload));
  for (const link of links) {
    body.append(renderItem(link, reload));
  }
}
