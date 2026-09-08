import assert from "node:assert/strict";
import test from "node:test";

import { ApiRequestError, apiRequestError } from "./apiRequestError.ts";

test("API request errors preserve status and safe server detail for recovery decisions", () => {
  const error = apiRequestError(
    409,
    "Finish or cancel the active Debate before starting another",
  );
  assert.ok(error instanceof ApiRequestError);
  assert.equal(error.status, 409);
  assert.equal(error.detail, "Finish or cancel the active Debate before starting another");
  assert.equal(error.message, error.detail);
});

test("API request errors keep status-specific safe fallbacks", () => {
  assert.equal(apiRequestError(401, "provider detail").message, "Your session is missing or expired. Sign in again and retry.");
  assert.equal(apiRequestError(503).message, "A live service is temporarily unavailable. Retry shortly.");
  assert.equal(apiRequestError(418).message, "The API request failed (418).");
});
