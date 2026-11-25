// @ts-check

import {
  deleteQueued,
  extractQueue,
  getQueue,
  importQueue,
  lookUpCaption,
  pasteCaption,
} from "../api/client.js";
import { extractPostLinks, summarize } from "../lib/queueLinks.js";
import { addLinks, readWaitingCaptions } from "./queueCapture.js";

/** @typedef {import("../api/client.js").PendingLink} PendingLink */

const STATUS_LABEL = /** @type {Record<string, string>} */ ({
  new: "Needs caption",
  ready: "Ready",
  extracting: "Extracting…",
  imported: "Imported",
  failed: "Failed",
});

/**
 * What to tell the owner after a caption lookup, by outcome.
 * @type {Record<string, string>}
 */
const LOOKUP_MESSAGE = {
  found: "Caption found. It is ready to extract.",
  no_caption: "This post has no caption. Paste the recipe from the comments or its website.",
  login_wall: "Instagram asked for a login. Paste the caption, or try again later.",
  rate_limited: "Instagram is limiting requests. Paste the caption, or try again later.",
  not_found: "Instagram says this post does not exist or is private.",
  failed: "Could not read the post. Paste the caption, or try again.",
};

/**
 * The message for a lookup outcome, or "" when no lookup ran.
 * @param {string | null | undefined} outcome
 * @returns {string}
 */
export function lookupMessage(outcome) {
  if (!outcome) {
    return "";
  }
  return LOOKUP_MESSAGE[outcome] ?? LOOKUP_MESSAGE.failed;
}

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
 * @param {(notice?: string) => void} reload
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
    void deleteQueued(link.code).then(() => reload());
  });
  head.append(open, status, remove);
  item.append(head);

  if (link.caption === null) {
    const form = document.createElement("form");
    form.className = "queue__caption-form";
    const area = document.createElement("textarea");
    area.className = "queue__caption-input";
    area.rows = 3;
    area.placeholder = "Paste the caption, or the recipe from the comments or a website…";
    area.setAttribute("aria-label", `Caption for ${link.code}`);
    const save = document.createElement("button");
    save.type = "submit";
    save.className = "queue__save";
    save.textContent = "Save caption";
    const find = document.createElement("button");
    find.type = "button";
    find.className = "queue__find";
    find.textContent = "Read it from Instagram";
    find.addEventListener("click", () => {
      find.disabled = true;
      find.textContent = "Reading…";
      lookUpCaption(link.code)
        .then((updated) => reload(lookupMessage(updated.caption_lookup)))
        .catch(() => reload(lookupMessage("failed")));
    });
    const actions = el("div", "queue__caption-actions");
    actions.append(save, find);
    form.append(area, actions);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (area.value.trim() === "") {
        return;
      }
      void pasteCaption(link.code, area.value.trim()).then(() => reload());
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
 * @param {(notice?: string) => void} reload
 * @returns {HTMLElement}
 */
function buildToolbar(links, reload) {
  const ready = links.filter((link) => link.status === "ready").length;
  const extracting = links.filter((link) => link.status === "extracting").length;
  const waiting = links.filter((link) => link.status === "new" && link.caption === null);

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

  const read = document.createElement("button");
  read.type = "button";
  read.className = "queue__batch-btn queue__batch-btn--quiet";
  read.textContent = waiting.length > 0 ? `Read captions (${waiting.length})` : "Read captions";
  read.disabled = waiting.length === 0;
  read.addEventListener("click", () => {
    for (const control of bar.querySelectorAll("button")) {
      /** @type {HTMLButtonElement} */ (control).disabled = true;
    }
    void readWaitingCaptions(waiting, (done, total) => {
      status.textContent = `Reading caption ${done} of ${total}…`;
    }).then((tally) => reload(summarize(tally)));
  });

  bar.append(
    read,
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
 * @param {string} [notice] a message from the last action, shown under the form
 */
export async function renderQueue(container, notice = "") {
  const page = el("div", "queue");
  const title = el("h1", "queue__title");
  title.textContent = "Queue";

  const addForm = document.createElement("form");
  addForm.className = "queue__add";
  const urls = document.createElement("textarea");
  urls.rows = 2;
  urls.placeholder = "Paste one or more Instagram links…";
  urls.className = "queue__add-input";
  urls.setAttribute("aria-label", "Instagram links, one or more");
  const add = document.createElement("button");
  add.type = "submit";
  add.className = "queue__add-btn";
  add.textContent = "Add";
  addForm.append(urls, add);

  const body = el("div", "queue__body");
  /** @param {string} [message] */
  const reload = (message) => {
    void renderQueue(container, message);
  };
  const status = el("p", "queue__notice");
  status.setAttribute("role", "status");
  status.textContent = notice;
  urls.addEventListener("input", () => urls.setCustomValidity(""));
  addForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const found = extractPostLinks(urls.value);
    if (found.length === 0) {
      urls.setCustomValidity("Paste at least one Instagram post or reel link.");
      urls.reportValidity();
      return;
    }
    // Each caption waits on Instagram, so a long list takes a while: keep the
    // page open until the summary appears.
    add.disabled = true;
    add.textContent = "Adding…";
    void addLinks(found, (done, total) => {
      status.textContent =
        total === 1
          ? "Adding the link and reading its caption…"
          : `Adding ${done} of ${total} and reading captions… keep this page open.`;
    }).then((tally) => reload(summarize(tally)));
  });

  page.append(title, addForm, status, body);
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
      stateMsg(
        "Nothing queued. Paste Instagram links above, as many as you like: their captions are read for you when Instagram allows it.",
      ),
    );
    return;
  }

  body.append(buildToolbar(links, reload));
  for (const link of links) {
    body.append(renderItem(link, reload));
  }
}
