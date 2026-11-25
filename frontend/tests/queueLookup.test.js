import assert from "node:assert/strict";
import { test } from "node:test";

import { lookupMessage } from "../js/views/queue.js";

test("lookupMessage explains each outcome, and stays quiet when none ran", () => {
  assert.equal(lookupMessage(null), "");
  assert.equal(lookupMessage(undefined), "");
  assert.match(lookupMessage("found"), /ready to extract/);
  assert.match(lookupMessage("login_wall"), /Paste the caption/);
  assert.match(lookupMessage("something_new"), /Could not read the post/);
});
