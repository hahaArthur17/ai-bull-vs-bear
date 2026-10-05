import assert from "node:assert/strict";
import test from "node:test";

import {
  activeInterruptionDraft,
  canStopBeforeOutput,
  canStopVisibleDraft,
  findInterjection,
  findInterruptedMessage,
  interruptionIdempotencyKey,
  shouldReconnectAfterInterruptionEnd,
  shouldStopBeforeOutput,
} from "./interruptionState.ts";
import type { DebateDraft, DebateStreamSnapshot } from "./debateStream.ts";
import type { DebateMessageRecord } from "./types.ts";

function snapshot(
  sessionStatus: DebateStreamSnapshot["sessionStatus"],
  activeGenerationId: string | null = "waiting-generation",
): DebateStreamSnapshot {
  return {
    status: "live",
    sessionStatus,
    canonicalMessages: [],
    drafts: {},
    lastSequence: 0,
    activeGenerationId,
    jobId: "job-1",
    jobStatus: "running",
    jobAttemptCount: 1,
    retryDelaySeconds: null,
    safeError: null,
  };
}

function record(overrides: Partial<DebateMessageRecord["message"]>): DebateMessageRecord {
  return {
    message: {
      id: "message-1",
      session_id: "session-1",
      branch_id: "branch-1",
      generation_id: "old-generation",
      sequence_number: 1,
      round_number: 1,
      exchange_number: 1,
      role: "bull",
      message_kind: "argument",
      content: "Visible prefix",
      terms: [],
      metadata: { interrupted: true },
      is_complete: false,
      cancelled_at: "2026-09-10T00:00:00Z",
      created_at: "2026-09-10T00:00:00Z",
      ...overrides,
    },
    citations: [],
  };
}

test("Stop remains available for a queued/running generation before its first draft", () => {
  assert.equal(canStopBeforeOutput(snapshot("queued_round_1")), true);
  assert.equal(canStopBeforeOutput(snapshot("running_round_2")), true);
  assert.equal(canStopBeforeOutput(snapshot("interrupted_awaiting_user")), false);
  assert.equal(canStopBeforeOutput(snapshot("running_round_1", null)), false);
});

test("Stop can freeze a displayed prefix after its provider turn became canonical", () => {
  const completed = record({
    generation_id: "waiting-generation",
    is_complete: true,
    metadata: {},
  });
  const current = { ...snapshot("running_round_2"), canonicalMessages: [completed] };
  const nextDraft: DebateDraft = {
    messageId: "message-2", generationId: "waiting-generation", role: "bear",
    content: "Visible next turn", nextDeltaIndex: 1, citations: [],
  };
  assert.equal(canStopBeforeOutput(current), false);
  assert.equal(shouldStopBeforeOutput(current), false);
  assert.equal(canStopVisibleDraft(current, nextDraft), true);
  assert.equal(canStopVisibleDraft(current, { ...nextDraft, messageId: "message-1" }), true);
});

test("visible Stop only accepts agent drafts during an interruptible phase", () => {
  const draft: DebateDraft = {
    messageId: "message-1",
    generationId: "waiting-generation",
    role: "bull",
    content: "prefix",
    nextDeltaIndex: 2,
    citations: [],
  };
  assert.equal(canStopVisibleDraft(snapshot("running_round_1"), draft), true);
  assert.equal(canStopVisibleDraft(snapshot("interrupted_awaiting_user"), draft), false);
  assert.equal(canStopVisibleDraft(snapshot("running_round_1"), { ...draft, role: "explainer" }), false);
});

test("Stop uses the received provider text even before the reveal scheduler renders it", () => {
  const displayedDraft: DebateDraft = {
    messageId: "message-1",
    generationId: "waiting-generation",
    role: "bull",
    content: "",
    nextDeltaIndex: 0,
    citations: [],
  };
  const receivedDraft = { ...displayedDraft, content: "Buffered but not rendered" };
  const current = { ...snapshot("running_round_1"), drafts: { [receivedDraft.messageId]: receivedDraft } };

  assert.equal(activeInterruptionDraft(current, displayedDraft)?.content, receivedDraft.content);
  assert.equal(shouldStopBeforeOutput(current, displayedDraft), false);
  assert.equal(activeInterruptionDraft(current)?.content, receivedDraft.content);
  assert.equal(shouldStopBeforeOutput(current), false);
  assert.equal(shouldStopBeforeOutput(snapshot("running_round_1")), true);
});

test("End reconnects until cancellation reaches a terminal session state", () => {
  assert.equal(shouldReconnectAfterInterruptionEnd("cancel_requested"), true);
  assert.equal(shouldReconnectAfterInterruptionEnd("cancelled"), false);
  assert.equal(shouldReconnectAfterInterruptionEnd("completed"), false);
  assert.equal(shouldReconnectAfterInterruptionEnd("failed"), false);
});

test("interjection lookup uses the post-Stop generation, preserving the frozen generation", () => {
  const interrupted = record({});
  const saved = record({
    id: "interjection-1",
    generation_id: "waiting-generation",
    role: "user",
    message_kind: "question",
    content: "Consider the downside.",
    metadata: { interjection: true, interrupted_message_id: "message-1" },
    is_complete: true,
  });
  const records = [interrupted, saved];

  assert.equal(findInterruptedMessage(records)?.message.id, "message-1");
  assert.equal(findInterjection(records, "message-1", "old-generation"), null);
  assert.equal(findInterjection(records, "message-1", "waiting-generation")?.message.id, "interjection-1");
});

test("interruption mutation keys are stable for safe retries and change with the input", () => {
  const identity = "old-generation:message-1:Consider the downside.";
  const first = interruptionIdempotencyKey("interject", identity);
  assert.equal(first, interruptionIdempotencyKey("interject", identity));
  assert.match(first, /^interject_[A-Za-z0-9]+$/);
  assert.notEqual(first, interruptionIdempotencyKey("interject", `${identity}!`));
  assert.notEqual(
    first,
    interruptionIdempotencyKey("interject", `new-waiting-generation:${identity}`),
  );
  assert.notEqual(first, interruptionIdempotencyKey("continue", identity));
});
