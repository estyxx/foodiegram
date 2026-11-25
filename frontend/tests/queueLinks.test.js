import assert from "node:assert/strict";
import { test } from "node:test";

import { emptyTally, extractPostLinks, isRefusal, summarize } from "../js/lib/queueLinks.js";

test("extractPostLinks finds post, reel and tv links in any pasted text", () => {
  const text = [
    "https://www.instagram.com/p/DJq4i8ysCL8/",
    "https://instagram.com/reel/C9abc_-12/?igsh=MWx0dGZ4",
    "look at this https://www.instagram.com/someone/p/XyZ123/ yum",
    "https://www.instagram.com/tv/TV1/",
    "https://www.instagram.com/someone/",
    "https://example.com/p/NOTIG/",
  ].join("\n");

  assert.deepEqual(extractPostLinks(text), [
    "https://www.instagram.com/p/DJq4i8ysCL8/",
    "https://www.instagram.com/p/C9abc_-12/",
    "https://www.instagram.com/p/XyZ123/",
    "https://www.instagram.com/p/TV1/",
  ]);
});

test("extractPostLinks drops repeats of the same post", () => {
  const text = "https://www.instagram.com/p/A1/ https://instagram.com/reel/A1/?x=1";
  assert.deepEqual(extractPostLinks(text), ["https://www.instagram.com/p/A1/"]);
});

test("isRefusal is true only when Instagram turns the server away", () => {
  assert.equal(isRefusal("login_wall"), true);
  assert.equal(isRefusal("rate_limited"), true);
  assert.equal(isRefusal("no_caption"), false);
  assert.equal(isRefusal(null), false);
});

test("summarize says what happened and what to do next", () => {
  assert.equal(summarize(emptyTally()), "Nothing to do.");
  assert.equal(
    summarize({ ...emptyTally(), ready: 3, known: 1 }),
    "3 captions read, 1 was already in the library. Launch extraction when you are ready.",
  );
  assert.match(
    summarize({ ...emptyTally(), ready: 1, waiting: 4, refused: true }),
    /^1 caption read, 4 links wait for a caption\. Instagram is refusing for now/,
  );
});
