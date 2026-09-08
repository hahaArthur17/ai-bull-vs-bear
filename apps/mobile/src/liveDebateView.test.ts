import assert from "node:assert/strict";
import test from "node:test";

import type { DebateStreamSnapshot } from "./debateStream.ts";
import {
  canCancelDebate,
  canChallengeDebate,
  debateMessageSections,
  debateStatusCopy,
} from "./liveDebateView.ts";
import type { DebateMessageRecord } from "./types.ts";

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

const record: DebateMessageRecord = {
  message: {
    id: "message-1",
    session_id: "session-1",
    branch_id: "branch-1",
    generation_id: "generation-1",
    sequence_number: 1,
    round_number: 1,
    exchange_number: 1,
    role: "bull",
    message_kind: "argument",
    content: "A server-authored bounded argument.",
    terms: [],
    metadata: {},
    is_complete: true,
    created_at: "2026-08-29T00:00:00Z",
  },
  citations: [
    {
      message_id: "message-1",
      evidence_id: "news-1",
      citation_order: 1,
      support_span: "Persisted support span.",
      metadata: {},
    },
  ],
  presentation: {
    argument: "A server-authored bounded argument.",
    interpretation: "A constructive reading of the frozen snapshot.",
    uncertainty: "Future evidence could change this reading.",
    facts_used: [
      {
        evidence_id: "news-1",
        evidence_type: "news",
        title: "Dated company update",
        fact: "A frozen evidence excerpt with the cited fact.",
        source: "Review fixture news",
        date: "2026-08-29T00:00:00Z",
        freshness: { status: "current", age_days: 1 },
        support_span: "Persisted support span.",
        source_destination: "https://example.com/evidence",
        missing_metadata: [],
      },
    ],
  },
};

test("queued and running jobs expose visible cancellable status", () => {
  assert.equal(debateStatusCopy(snapshot()).label, "Queued");
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
  assert.equal(debateStatusCopy(failed).label, "Failed safely");
  assert.equal(debateStatusCopy(failed).tone, "danger");
  assert.equal(canCancelDebate(failed), false);
});

test("terminal states use explicit cancelled and final labels", () => {
  assert.equal(debateStatusCopy(snapshot({ sessionStatus: "cancelled", jobStatus: "cancelled" })).label, "Cancelled");
  assert.equal(debateStatusCopy(snapshot({ sessionStatus: "completed", jobStatus: "stage_completed" })).label, "Final");
});

test("interim pause invites a question before an optional Round 2 challenge", () => {
  const copy = debateStatusCopy(snapshot({
    sessionStatus: "awaiting_user",
    jobStatus: "stage_completed",
  }));

  assert.equal(copy.label, "Waiting for your question");
  assert.match(copy.detail, /before deciding whether to continue to Round 2/i);
});

test("only the durable interim pause enables a round two challenge", () => {
  assert.equal(canChallengeDebate(snapshot()), false);
  assert.equal(canChallengeDebate(snapshot({
    sessionStatus: "awaiting_user",
    jobStatus: "stage_completed",
  })), true);
});

test("canonical Debate presentation exposes only server-authored facts and metadata", () => {
  const sections = debateMessageSections(record);

  assert.equal(sections.hasAuthoritativePresentation, true);
  assert.equal(sections.argument, record.message.content);
  assert.equal(sections.interpretation, record.presentation?.interpretation);
  assert.equal(sections.uncertainty, record.presentation?.uncertainty);
  assert.deepEqual(sections.factsUsed[0], {
    evidenceId: "news-1",
    evidenceType: "news",
    title: "Dated company update",
    fact: "A frozen evidence excerpt with the cited fact.",
    source: "Review fixture news",
    date: "Aug 29, 2026",
    freshness: "Current · 1d old",
    tone: "current",
    supportSpan: "Persisted support span.",
    sourceDestination: "https://example.com/evidence",
    missingMetadata: [],
  });
});

test("legacy records preserve their argument without inferring fact metadata from citations", () => {
  const sections = debateMessageSections({ ...record, presentation: null });

  assert.equal(sections.hasAuthoritativePresentation, false);
  assert.equal(sections.argument, record.message.content);
  assert.deepEqual(sections.factsUsed, []);
  assert.equal(sections.interpretation, null);
  assert.equal(sections.uncertainty, null);
});
