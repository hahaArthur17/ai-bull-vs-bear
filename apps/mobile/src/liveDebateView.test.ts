import assert from "node:assert/strict";
import test from "node:test";

import type { DebateStreamSnapshot } from "./debateStream.ts";
import {
  canCancelDebate,
  canChallengeDebate,
  debateStatusCopy,
} from "./liveDebateView.ts";

function snapshot(
  overrides: Partial<DebateStreamSnapshot> = {},
): DebateStreamSnapshot {
  return {
    status: "live",
    sessionStatus: "queued_round_1",
    canonicalMessages: [],
    drafts: {},
    lastSequence: 0,
    activeGenerationId: "generation-1",
    jobId: "job-1",
    jobStatus: "queued",
    jobAttemptCount: 0,
    retryDelaySeconds: null,
    safeError: null,
    ...overrides,
  };
}

test("queued and running jobs expose visible cancellable status", () => {
  assert.equal(debateStatusCopy(snapshot()).label, "Queued with backpressure");
  assert.equal(canCancelDebate(snapshot()), true);

  const running = snapshot({
    sessionStatus: "running_round_1",
    jobStatus: "running",
    jobAttemptCount: 2,
  });
  assert.match(debateStatusCopy(running).detail, /attempt 2/i);
  assert.equal(canCancelDebate(running), true);
});

test("retry delay and failure are presented without provider details", () => {
  const retry = snapshot({
    jobStatus: "retry_scheduled",
    jobAttemptCount: 1,
    retryDelaySeconds: 4,
  });
  assert.match(debateStatusCopy(retry).detail, /4s/);

  const failed = snapshot({ sessionStatus: "failed", jobStatus: "failed" });
  assert.equal(debateStatusCopy(failed).tone, "danger");
  assert.equal(canCancelDebate(failed), false);
});

test("only the durable interim pause enables a round two challenge", () => {
  assert.equal(canChallengeDebate(snapshot()), false);
  assert.equal(canChallengeDebate(snapshot({
    sessionStatus: "awaiting_user",
    jobStatus: "stage_completed",
  })), true);
});
