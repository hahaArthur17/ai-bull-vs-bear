import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_PENDING_INTERRUPTION_PREFIX_LENGTH,
  PENDING_INTERRUPTION_STORAGE_VERSION,
  clearPendingInterruptionsForAccount,
  confirmPendingInterruption,
  createPendingInterruption,
  loadPendingInterruption,
  savePendingInterruption,
} from "./pendingInterruption.ts";
import type { PendingInterruptionStorage } from "./pendingInterruption.ts";

function memoryStorage(): PendingInterruptionStorage & { values: Map<string, string> } {
  const values = new Map<string, string>();
  return {
    values,
    getItem: async (key) => values.get(key) || null,
    setItem: async (key, value) => { values.set(key, value); },
    removeItem: async (key) => { values.delete(key); },
  };
}

function pending(
  accountId = "account-1",
  sessionId = "session-1",
  visiblePrefix = "A visible, incomplete answer.",
) {
  return createPendingInterruption({
    accountId,
    sessionId,
    generationId: "generation-1",
    messageId: "message-1",
    visiblePrefix,
    role: "bull",
    precedingMessageIds: ["canonical-1", "canonical-2"],
  });
}

test("pending interruptions retain the exact Stop target and a stable idempotency key", async () => {
  const storage = memoryStorage();
  const first = pending();
  const sameTarget = pending();
  assert.equal(first.idempotencyKey, sameTarget.idempotencyKey);

  await savePendingInterruption(storage, first);
  assert.deepEqual(await loadPendingInterruption(storage, "account-1", "session-1"), first);
});

test("pending interruptions preserve an empty prefix and count Unicode code points", async () => {
  const storage = memoryStorage();
  const empty = pending("account-1", "session-empty", "");
  const maxUnicodePrefix = "😀".repeat(MAX_PENDING_INTERRUPTION_PREFIX_LENGTH);
  await savePendingInterruption(storage, empty);
  await savePendingInterruption(storage, pending("account-1", "session-unicode", maxUnicodePrefix));

  assert.deepEqual(await loadPendingInterruption(storage, "account-1", "session-empty"), empty);
  assert.throws(() => pending("account-1", "session-too-long", "😀".repeat(MAX_PENDING_INTERRUPTION_PREFIX_LENGTH + 1)));
});

test("pending interruptions retain display role and exactly the visible canonical message boundary", async () => {
  const storage = memoryStorage();
  const interruption = createPendingInterruption({
    accountId: "account-1",
    sessionId: "session-1",
    generationId: "generation-1",
    messageId: "message-1",
    visiblePrefix: "Frozen response.",
    role: "judge",
    precedingMessageIds: ["bull-1", "bear-1"],
  });
  await savePendingInterruption(storage, interruption);

  assert.deepEqual(await loadPendingInterruption(storage, "account-1", "session-1"), interruption);
});

test("legacy records recover only their prefix with a system role and no canonical messages", async () => {
  const storage = memoryStorage();
  const key = `ai-bull-vs-bear:pending-interruptions:v${PENDING_INTERRUPTION_STORAGE_VERSION}:account-1`;
  storage.values.set(key, JSON.stringify({
    version: PENDING_INTERRUPTION_STORAGE_VERSION,
    entries: {
      "session-1": {
        accountId: "account-1",
        sessionId: "session-1",
        generationId: "generation-1",
        messageId: "message-1",
        visiblePrefix: "Legacy prefix.",
        idempotencyKey: "interrupt_legacy",
      },
    },
  }));

  const recovered = await loadPendingInterruption(storage, "account-1", "session-1");
  assert.equal(recovered?.role, "system");
  assert.deepEqual(recovered?.precedingMessageIds, []);
  assert.equal(recovered?.visiblePrefix, "Legacy prefix.");
});

test("pending interruptions are isolated by account and session", async () => {
  const storage = memoryStorage();
  const first = pending("account-1", "session-1");
  const second = pending("account-1", "session-2", "Another prefix.");
  const otherAccount = pending("account-2", "session-1", "Other account prefix.");
  await savePendingInterruption(storage, first);
  await savePendingInterruption(storage, second);
  await savePendingInterruption(storage, otherAccount);

  assert.deepEqual(await loadPendingInterruption(storage, "account-1", "session-1"), first);
  assert.deepEqual(await loadPendingInterruption(storage, "account-1", "session-2"), second);
  assert.deepEqual(await loadPendingInterruption(storage, "account-2", "session-1"), otherAccount);
  assert.equal(await loadPendingInterruption(storage, "account-2", "session-2"), null);
});

test("confirmation removes only the confirmed session's pending Stop", async () => {
  const storage = memoryStorage();
  const first = pending("account-1", "session-1");
  const second = pending("account-1", "session-2");
  await savePendingInterruption(storage, first);
  await savePendingInterruption(storage, second);

  assert.equal(await confirmPendingInterruption(storage, "account-1", "session-1", first.idempotencyKey), true);
  assert.equal(await loadPendingInterruption(storage, "account-1", "session-1"), null);
  assert.deepEqual(await loadPendingInterruption(storage, "account-1", "session-2"), second);
});

test("a late confirmation cannot delete a newer pending Stop", async () => {
  const storage = memoryStorage();
  const original = pending("account-1", "session-1", "First visible prefix.");
  const replacement = pending("account-1", "session-1", "New visible prefix.");
  await savePendingInterruption(storage, original);
  await savePendingInterruption(storage, replacement);

  assert.equal(await confirmPendingInterruption(storage, "account-1", "session-1", original.idempotencyKey), false);
  assert.deepEqual(await loadPendingInterruption(storage, "account-1", "session-1"), replacement);
});

test("prototype-like session identifiers remain isolated records", async () => {
  const storage = memoryStorage();
  const specialSession = pending("account-1", "__proto__", "First character stopped.");
  await savePendingInterruption(storage, specialSession);

  assert.deepEqual(await loadPendingInterruption(storage, "account-1", "__proto__"), specialSession);
  assert.equal(await confirmPendingInterruption(storage, "account-1", "__proto__", specialSession.idempotencyKey), true);
  assert.equal(await loadPendingInterruption(storage, "account-1", "__proto__"), null);
});

test("account sign-out clears every pending Stop for that account only", async () => {
  const storage = memoryStorage();
  await savePendingInterruption(storage, pending("account-1", "session-1"));
  const otherAccount = pending("account-2", "session-1");
  await savePendingInterruption(storage, otherAccount);

  await clearPendingInterruptionsForAccount(storage, "account-1");
  assert.equal(await loadPendingInterruption(storage, "account-1", "session-1"), null);
  assert.deepEqual(await loadPendingInterruption(storage, "account-2", "session-1"), otherAccount);
});

test("invalid versions, shapes, and oversized prefixes are discarded", async () => {
  const storage = memoryStorage();
  const key = `ai-bull-vs-bear:pending-interruptions:v${PENDING_INTERRUPTION_STORAGE_VERSION}:account-1`;
  storage.values.set(key, JSON.stringify({ version: 999, entries: {} }));
  assert.equal(await loadPendingInterruption(storage, "account-1", "session-1"), null);
  assert.equal(storage.values.has(key), false);

  storage.values.set(key, JSON.stringify({
    version: PENDING_INTERRUPTION_STORAGE_VERSION,
    entries: { "session-1": { accountId: "account-2" } },
  }));
  assert.equal(await loadPendingInterruption(storage, "account-1", "session-1"), null);
  assert.equal(storage.values.has(key), false);

  assert.throws(() => pending("account-1", "session-1", "x".repeat(MAX_PENDING_INTERRUPTION_PREFIX_LENGTH + 1)));
  assert.throws(() => createPendingInterruption({
    accountId: "account-1", sessionId: "session-1", generationId: "generation-1", messageId: "message-1",
    visiblePrefix: "x", role: "bull", precedingMessageIds: Array.from({ length: 101 }, (_, index) => `message-${index}`),
  }));
});
