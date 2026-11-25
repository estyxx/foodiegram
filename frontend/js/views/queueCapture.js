// @ts-check

import { ApiError, lookUpCaption, queueLink } from "../api/client.js";
import { emptyTally, isRefusal } from "../lib/queueLinks.js";

/** @typedef {import("../lib/queueLinks.js").Tally} Tally */
/** @typedef {import("../api/client.js").PendingLink} PendingLink */

/** Space between two requests to Instagram, as IGbulkDL leaves between posts. */
const PAUSE_MS = 1500;
/** HTTP status the queue answers for a post that is already a recipe. */
const ALREADY_IN_LIBRARY = 409;

/**
 * @param {number} ms
 * @returns {Promise<void>}
 */
function pause(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

/**
 * @param {Tally} tally
 * @param {PendingLink} link
 */
function record(tally, link) {
  if (link.caption) {
    tally.ready += 1;
  } else {
    tally.waiting += 1;
  }
  if (isRefusal(link.caption_lookup)) {
    tally.refused = true;
  }
}

/**
 * Queue each link in turn, reading captions until Instagram starts refusing;
 * after that the rest are queued without asking it.
 * @param {string[]} urls
 * @param {(done: number, total: number) => void} onProgress
 * @returns {Promise<Tally>}
 */
export async function addLinks(urls, onProgress) {
  const tally = emptyTally();
  for (const [index, url] of urls.entries()) {
    onProgress(index + 1, urls.length);
    const asked = !tally.refused;
    try {
      record(tally, await queueLink(url, { readCaption: asked }));
    } catch (error) {
      if (error instanceof ApiError && error.status === ALREADY_IN_LIBRARY) {
        tally.known += 1;
      } else {
        tally.broken += 1;
      }
    }
    if (asked && index < urls.length - 1) {
      await pause(PAUSE_MS);
    }
  }
  return tally;
}

/**
 * Read the caption of every link still waiting for one, stopping as soon as
 * Instagram refuses.
 * @param {PendingLink[]} waiting
 * @param {(done: number, total: number) => void} onProgress
 * @returns {Promise<Tally>}
 */
export async function readWaitingCaptions(waiting, onProgress) {
  const tally = emptyTally();
  for (const [index, link] of waiting.entries()) {
    onProgress(index + 1, waiting.length);
    try {
      record(tally, await lookUpCaption(link.code));
    } catch {
      tally.broken += 1;
    }
    if (tally.refused) {
      // The links not asked still wait for a caption.
      tally.waiting += waiting.length - index - 1;
      break;
    }
    if (index < waiting.length - 1) {
      await pause(PAUSE_MS);
    }
  }
  return tally;
}
