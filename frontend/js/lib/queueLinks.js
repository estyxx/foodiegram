// @ts-check

/**
 * An Instagram post, reel or IGTV link, with or without a username before it
 * and with any tracking query after it. The shortcode is the one capture group.
 */
const POST_LINK =
  /https?:\/\/(?:www\.)?instagram\.com\/(?:[A-Za-z0-9_.]+\/)?(?:p|reel|tv)\/([A-Za-z0-9_-]+)/g;

/** Outcomes that mean Instagram is turning the server away for now. */
const REFUSALS = new Set(["login_wall", "rate_limited"]);

/**
 * Every distinct post link in a pasted text, in order, as canonical post URLs.
 * Accepts one link per line, a list exported from a browser extension, or
 * links buried in a message.
 * @param {string} text
 * @returns {string[]}
 */
export function extractPostLinks(text) {
  /** @type {Set<string>} */
  const seen = new Set();
  /** @type {string[]} */
  const links = [];
  for (const match of text.matchAll(POST_LINK)) {
    const code = match[1];
    if (!seen.has(code)) {
      seen.add(code);
      links.push(`https://www.instagram.com/p/${code}/`);
    }
  }
  return links;
}

/**
 * True when a lookup outcome means Instagram is refusing the server, so the
 * remaining links should be queued without asking it again.
 * @param {string | null | undefined} outcome
 * @returns {boolean}
 */
export function isRefusal(outcome) {
  return outcome !== null && outcome !== undefined && REFUSALS.has(outcome);
}

/**
 * Running totals for one pass over a list of links.
 * @typedef {object} Tally
 * @property {number} ready links that now have a caption
 * @property {number} waiting links still waiting for a caption
 * @property {number} known links already in the library
 * @property {number} broken links the server would not take
 * @property {boolean} refused Instagram started refusing during the pass
 */

/** @returns {Tally} */
export function emptyTally() {
  return { ready: 0, waiting: 0, known: 0, broken: 0, refused: false };
}

/**
 * @param {number} n
 * @param {string} one
 * @param {string} many
 * @returns {string}
 */
function count(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

/**
 * One sentence on how a pass went, and what to do next.
 * @param {Tally} tally
 * @returns {string}
 */
export function summarize(tally) {
  /** @type {string[]} */
  const parts = [];
  if (tally.ready > 0) {
    parts.push(`${count(tally.ready, "caption", "captions")} read`);
  }
  if (tally.waiting > 0) {
    parts.push(`${count(tally.waiting, "link waits", "links wait")} for a caption`);
  }
  if (tally.known > 0) {
    parts.push(`${count(tally.known, "was", "were")} already in the library`);
  }
  if (tally.broken > 0) {
    parts.push(`${count(tally.broken, "link", "links")} could not be added`);
  }
  if (parts.length === 0) {
    return "Nothing to do.";
  }
  let sentence = `${parts.join(", ")}.`;
  sentence = sentence.charAt(0).toUpperCase() + sentence.slice(1);
  if (tally.refused) {
    sentence +=
      " Instagram is refusing for now: paste those captions, or press “Read captions” again in a while.";
  } else if (tally.ready > 0) {
    sentence += " Launch extraction when you are ready.";
  }
  return sentence;
}
