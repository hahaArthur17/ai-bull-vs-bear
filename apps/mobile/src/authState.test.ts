import assert from "node:assert/strict";
import test from "node:test";

import { isAuthenticationButtonSubmitting } from "./authState.ts";

test("authentication submission state belongs only to the submitted action", () => {
  assert.equal(isAuthenticationButtonSubmitting("sign-in", "sign-in"), true);
  assert.equal(isAuthenticationButtonSubmitting("sign-in", "sign-up"), false);
  assert.equal(isAuthenticationButtonSubmitting("sign-up", "sign-in"), false);
  assert.equal(isAuthenticationButtonSubmitting("sign-up", "sign-up"), true);
  assert.equal(isAuthenticationButtonSubmitting(null, "sign-in"), false);
});
