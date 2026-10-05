import assert from "node:assert/strict";
import test from "node:test";

import { hasEarlierUnverifiedGroqMessages } from "./legacyGrounding.ts";

test("old live Groq messages trigger a source verification warning", () => {
  assert.equal(hasEarlierUnverifiedGroqMessages([
    { message: { metadata: { provider: "groq-live-debate", provider_version: "v1" } } },
  ]), true);
  assert.equal(hasEarlierUnverifiedGroqMessages([
    { message: { metadata: { provider: "groq-live-judge", provider_version: "v1" } } },
  ]), true);
});

test("new or deterministic messages do not trigger the old-run warning", () => {
  assert.equal(hasEarlierUnverifiedGroqMessages([
    { message: { metadata: { provider: "groq-live-debate", provider_version: "v2" } } },
    { message: { metadata: { provider: "deterministic-debate", provider_version: "v1" } } },
  ]), false);
});
