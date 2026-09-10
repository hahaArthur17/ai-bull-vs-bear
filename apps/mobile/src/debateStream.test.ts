import assert from "node:assert/strict";
import test from "node:test";

import {
  DebateCursorExpiredError,
  DebateStreamClient,
  SseFrameParser,
  createCanonicalDebateSnapshot,
  reduceDebateEvent,
} from "./debateStream.ts";
import type { DebateStreamSnapshot } from "./debateStream.ts";
import type {
  DebateEvent,
  DebateMessage,
  DebateSessionDetail,
} from "./types";


function event(
  sequence: number,
  type: DebateEvent["type"],
  payload: Record<string, unknown>,
): DebateEvent {
  return {
    version: 1,
    event_id: `event-${sequence}`,
    session_id: "session-1",
    sequence,
    type,
    timestamp: "2026-08-28T00:00:00Z",
    payload,
  };
}


function message(content: string): DebateMessage {
  return {
    id: "message-1",
    session_id: "session-1",
    branch_id: "branch-1",
    generation_id: "generation-1",
    sequence_number: 1,
    round_number: 1,
    exchange_number: 1,
    role: "bull",
    message_kind: "argument",
    content,
    confidence: "medium",
    signal_strength: "medium",
    terms: ["momentum"],
    metadata: {},
    is_complete: true,
    created_at: "2026-08-28T00:00:00Z",
  };
}


function detail(status: DebateSessionDetail["session"]["status"]): DebateSessionDetail {
  return {
    session: {
      id: "session-1",
      ticker: "AAPL",
      status,
      active_branch_id: "branch-1",
      active_generation_id: "generation-1",
      opening_side: "bull",
      created_at: "2026-08-28T00:00:00Z",
      updated_at: "2026-08-28T00:00:00Z",
    },
    messages: [],
    execution_mode: "synchronous_preview",
  };
}


test("SSE parser preserves fragmented multi-line data", () => {
  const parser = new SseFrameParser();

  assert.deepEqual(parser.push("id: 1\nevent: turn.delta\ndata: {\"a\":"), []);
  assert.deepEqual(parser.push("1}\n\n"), [
    { id: "1", event: "turn.delta", data: "{\"a\":1}" },
  ]);
  assert.deepEqual(parser.push(": heartbeat comment\r\ndata: first\r\ndata: second\r\n\r\n"), [
    { id: null, event: "message", data: "first\nsecond" },
  ]);
});


test("reducer keeps deltas temporary and replaces them with canonical completion", () => {
  let snapshot: DebateStreamSnapshot = {
    status: "live",
    sessionStatus: "running_round_1",
    canonicalMessages: [],
    drafts: {},
    lastSequence: 0,
    activeGenerationId: "generation-1",
    jobId: null,
    jobStatus: "none",
    jobAttemptCount: 0,
    retryDelaySeconds: null,
    safeError: null,
  };
  snapshot = reduceDebateEvent(snapshot, event(1, "turn.started", {
    message_id: "message-1",
    generation_id: "generation-1",
    role: "bull",
  })).snapshot;
  snapshot = reduceDebateEvent(snapshot, event(2, "turn.delta", {
    message_id: "message-1",
    generation_id: "generation-1",
    delta_index: 1,
    delta: "Grounded ",
  })).snapshot;
  snapshot = reduceDebateEvent(snapshot, event(3, "turn.delta", {
    message_id: "message-1",
    generation_id: "generation-1",
    delta_index: 2,
    delta: "argument.",
  })).snapshot;
  snapshot = reduceDebateEvent(snapshot, event(4, "turn.citation", {
    message_id: "message-1",
    generation_id: "generation-1",
    evidence_id: "news-1",
    citation_order: 1,
    support_span: "Persisted evidence span.",
  })).snapshot;

  assert.equal(snapshot.drafts["message-1"].content, "Grounded argument.");
  assert.equal(snapshot.canonicalMessages.length, 0);

  snapshot = reduceDebateEvent(snapshot, event(5, "turn.completed", {
    generation_id: "generation-1",
    message: message("Grounded argument."),
    presentation: {
      argument: "Grounded argument.",
      facts_used: [
        {
          evidence_id: "news-1",
          evidence_type: "news",
          title: "Dated evidence",
          fact: "A frozen evidence excerpt.",
          source: "Review fixture news",
          date: "2026-08-28T00:00:00Z",
          freshness: { status: "current", age_days: 0 },
          support_span: "Persisted evidence span.",
          source_destination: "https://example.com/evidence",
          missing_metadata: [],
        },
      ],
      interpretation: "A bounded reading of the snapshot.",
      uncertainty: "Future evidence can change this reading.",
    },
  })).snapshot;

  assert.deepEqual(snapshot.drafts, {});
  assert.equal(snapshot.canonicalMessages[0].message.content, "Grounded argument.");
  assert.equal(snapshot.canonicalMessages[0].citations[0].evidence_id, "news-1");
  assert.equal(snapshot.canonicalMessages[0].citations[0].support_span, "Persisted evidence span.");
  assert.equal(snapshot.canonicalMessages[0].presentation?.facts_used[0].evidence_id, "news-1");
});


test("reducer retains loaded presentation when a compatible retained event omits it", () => {
  const loadedPresentation = {
    argument: "Already loaded canonical argument.",
    facts_used: [],
    interpretation: null,
    uncertainty: null,
  };
  const snapshot: DebateStreamSnapshot = {
    status: "live",
    sessionStatus: "running_round_1",
    canonicalMessages: [{
      message: message("Already loaded canonical argument."),
      citations: [],
      presentation: loadedPresentation,
    }],
    drafts: {},
    lastSequence: 0,
    activeGenerationId: "generation-1",
    jobId: null,
    jobStatus: "none",
    jobAttemptCount: 0,
    retryDelaySeconds: null,
    safeError: null,
  };

  const reduced = reduceDebateEvent(snapshot, event(1, "turn.completed", {
    generation_id: "generation-1",
    message: message("Already loaded canonical argument."),
  }));

  assert.deepEqual(reduced.snapshot.canonicalMessages[0].presentation, loadedPresentation);
});

test("deterministic Judge completion and future ordered Judge deltas both preserve the draft contract", () => {
  let snapshot: DebateStreamSnapshot = {
    status: "live", sessionStatus: "running_round_1", canonicalMessages: [], drafts: {}, lastSequence: 0,
    activeGenerationId: "generation-1", jobId: null, jobStatus: "running", jobAttemptCount: 1,
    retryDelaySeconds: null, safeError: null,
  };
  snapshot = reduceDebateEvent(snapshot, event(1, "judge.started", {
    message_id: "message-1", generation_id: "generation-1",
  })).snapshot;
  snapshot = reduceDebateEvent(snapshot, event(2, "judge.completed", {
    generation_id: "generation-1", message: { ...message("Deterministic Judge."), role: "judge" },
  })).snapshot;
  assert.equal(snapshot.canonicalMessages[0].message.content, "Deterministic Judge.");

  snapshot = { ...snapshot, canonicalMessages: [], drafts: {}, lastSequence: 0 };
  snapshot = reduceDebateEvent(snapshot, event(1, "judge.started", {
    message_id: "message-1", generation_id: "generation-1",
  })).snapshot;
  snapshot = reduceDebateEvent(snapshot, event(2, "judge.delta", {
    message_id: "message-1", generation_id: "generation-1", delta_index: 1, delta: "Streaming Judge.",
  })).snapshot;
  snapshot = reduceDebateEvent(snapshot, event(3, "judge.completed", {
    generation_id: "generation-1", message: { ...message("Streaming Judge."), role: "judge" },
  })).snapshot;
  assert.equal(snapshot.canonicalMessages[0].message.content, "Streaming Judge.");
});


test("reducer rejects a missing event or provider delta", () => {
  const snapshot: DebateStreamSnapshot = {
    status: "live",
    sessionStatus: "running_round_1",
    canonicalMessages: [],
    drafts: {},
    lastSequence: 4,
    activeGenerationId: "generation-1",
    jobId: null,
    jobStatus: "none",
    jobAttemptCount: 0,
    retryDelaySeconds: null,
    safeError: null,
  };

  assert.throws(() => reduceDebateEvent(snapshot, event(6, "turn.delta", {
    message_id: "message-1",
    generation_id: "generation-1",
    delta_index: 2,
    delta: "late",
  })));
});


test("reducer advances past a late event without mutating the active generation", () => {
  const snapshot: DebateStreamSnapshot = {
    status: "live",
    sessionStatus: "running_round_1",
    canonicalMessages: [],
    drafts: {
      "message-1": {
        messageId: "message-1",
        generationId: "generation-1",
        role: "bull",
        content: "current",
        nextDeltaIndex: 2,
        citations: [],
      },
    },
    lastSequence: 3,
    activeGenerationId: "generation-1",
    jobId: null,
    jobStatus: "none",
    jobAttemptCount: 0,
    retryDelaySeconds: null,
    safeError: null,
  };

  const reduced = reduceDebateEvent(snapshot, event(4, "turn.delta", {
    message_id: "old-message",
    generation_id: "old-generation",
    delta_index: 99,
    delta: "must be ignored",
  }));

  assert.equal(reduced.snapshot.lastSequence, 4);
  assert.equal(reduced.snapshot.drafts["message-1"].content, "current");
  assert.equal(reduced.snapshot.drafts["old-message"], undefined);
});


test("reducer exposes queued running retry and failure job states", () => {
  let snapshot: DebateStreamSnapshot = {
    status: "live",
    sessionStatus: "running_round_1",
    canonicalMessages: [],
    drafts: {},
    lastSequence: 0,
    activeGenerationId: "generation-1",
    jobId: null,
    jobStatus: "none",
    jobAttemptCount: 0,
    retryDelaySeconds: null,
    safeError: null,
  };

  snapshot = reduceDebateEvent(snapshot, event(1, "job.queued", {
    job_id: "job-1",
    generation_id: "generation-1",
  })).snapshot;
  assert.equal(snapshot.jobStatus, "queued");
  assert.equal(snapshot.jobId, "job-1");

  snapshot = reduceDebateEvent(snapshot, event(2, "job.started", {
    job_id: "job-1",
    generation_id: "generation-1",
    attempt_count: 1,
  })).snapshot;
  assert.equal(snapshot.jobStatus, "running");
  assert.equal(snapshot.jobAttemptCount, 1);

  snapshot = reduceDebateEvent(snapshot, event(3, "job.retry_scheduled", {
    job_id: "job-1",
    generation_id: "generation-1",
    attempt_count: 1,
    retry_delay_seconds: 4,
  })).snapshot;
  assert.equal(snapshot.jobStatus, "retry_scheduled");
  assert.equal(snapshot.retryDelaySeconds, 4);

  snapshot = reduceDebateEvent(snapshot, event(4, "job.failed", {
    job_id: "job-1",
    generation_id: "generation-1",
    attempt_count: 3,
    safe_error_code: "debate_retry_exhausted",
  })).snapshot;
  assert.equal(snapshot.jobStatus, "failed");
  assert.equal(snapshot.jobAttemptCount, 3);
  assert.equal(snapshot.retryDelaySeconds, null);
});


test("cancellation rotates generation, clears drafts, and ignores late output", () => {
  const snapshot: DebateStreamSnapshot = {
    status: "live",
    sessionStatus: "running_round_1",
    canonicalMessages: [],
    drafts: {
      "message-1": {
        messageId: "message-1",
        generationId: "generation-1",
        role: "bull",
        content: "partial output",
        nextDeltaIndex: 2,
        citations: [],
      },
    },
    lastSequence: 3,
    activeGenerationId: "generation-1",
    jobId: "job-1",
    jobStatus: "running",
    jobAttemptCount: 1,
    retryDelaySeconds: null,
    safeError: null,
  };

  const requested = reduceDebateEvent(snapshot, event(4, "session.cancel_requested", {
    status: "cancel_requested",
    cancelled_generation_id: "generation-1",
    generation_id: "cancel-generation",
  }));
  assert.equal(requested.terminal, false);
  assert.equal(requested.snapshot.activeGenerationId, "cancel-generation");
  assert.deepEqual(requested.snapshot.drafts, {});

  const late = reduceDebateEvent(requested.snapshot, event(5, "turn.delta", {
    message_id: "message-1",
    generation_id: "generation-1",
    delta_index: 2,
    delta: " that must be ignored",
  }));
  assert.equal(late.snapshot.lastSequence, 5);
  assert.deepEqual(late.snapshot.drafts, {});

  const cancelled = reduceDebateEvent(late.snapshot, event(6, "session.cancelled", {
    status: "cancelled",
    generation_id: "cancel-generation",
  }));
  assert.equal(cancelled.terminal, true);
  assert.equal(cancelled.snapshot.status, "closed");
  assert.equal(cancelled.snapshot.sessionStatus, "cancelled");
});


test("canonical snapshot exposes durable session and queued job state", () => {
  const queued = detail("queued_round_1");
  queued.execution_mode = "queued";
  queued.job = {
    id: "job-1",
    session_id: "session-1",
    job_type: "round_1",
    status: "queued",
    queue_message_id: 7,
    attempt_count: 0,
    max_attempts: 3,
  };

  const snapshot = createCanonicalDebateSnapshot(queued);

  assert.equal(snapshot.status, "connecting");
  assert.equal(snapshot.sessionStatus, "queued_round_1");
  assert.equal(snapshot.jobStatus, "queued");
  assert.equal(snapshot.jobId, "job-1");
});


test("client reloads canonical state at the server recovery cursor", async () => {
  let openCount = 0;
  const cursors: number[] = [];
  const snapshots: number[] = [];
  const client = new DebateStreamClient({
    eventUrl: "https://example.test/debates/session-1/events",
    getAccessToken: async () => "access-token",
    loadCanonical: async () => detail("running_round_1"),
    onSnapshot: (snapshot) => snapshots.push(snapshot.lastSequence),
    transport: {
      open: async (options) => {
        cursors.push(options.afterSequence);
        openCount += 1;
        if (openCount === 1) throw new DebateCursorExpiredError(7);
        options.onEvent(event(8, "session.awaiting_user", {
          generation_id: "generation-1",
          status: "awaiting_user",
        }));
      },
    },
  });

  await client.start();

  assert.deepEqual(cursors, [0, 7]);
  assert.equal(snapshots.at(-1), 8);
});

test("an interruption from another client reloads the shortened canonical transcript", async () => {
  let loads = 0;
  const received: DebateStreamSnapshot[] = [];
  const client = new DebateStreamClient({
    eventUrl: "https://example.test/events", getAccessToken: async () => "test-token",
    loadCanonical: async () => {
      loads += 1;
      return detail(loads === 1 ? "running_round_1" : "interrupted_awaiting_user");
    },
    onSnapshot: (snapshot) => received.push(snapshot),
    transport: { open: async (options) => {
      options.onEvent(event(1, "session.interrupted_awaiting_user", {
        status: "interrupted_awaiting_user", generation_id: "new-generation",
      }));
    } },
  });
  await client.start();
  assert.equal(loads, 2);
  assert.equal(received.at(-1)?.sessionStatus, "interrupted_awaiting_user");
  assert.deepEqual(received.at(-1)?.drafts, {});
});
