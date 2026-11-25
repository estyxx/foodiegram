import assert from "node:assert/strict";
import { test } from "node:test";

import { buildId, isNewBuild } from "../js/lib/appUpdate.js";

test("buildId prefers the commit, then the deployment, then the version", () => {
  assert.equal(buildId({ version: "2026.11.1", commit: "abc1234", deployment: "d1" }), "abc1234");
  assert.equal(buildId({ version: "2026.11.1", commit: "", deployment: "cc73c5ee" }), "cc73c5ee");
  assert.equal(buildId({ version: "2026.11.1", commit: "", deployment: "" }), "2026.11.1");
});

test("isNewBuild only fires on a real change", () => {
  assert.equal(isNewBuild("cc73c5ee", "dd84d6ff"), true);
  assert.equal(isNewBuild("cc73c5ee", "cc73c5ee"), false);
  assert.equal(isNewBuild("", "dd84d6ff"), false);
});
