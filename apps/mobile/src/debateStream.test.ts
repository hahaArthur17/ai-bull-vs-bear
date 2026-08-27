import assert from "node:assert/strict";
import test from "node:test";

import {
  DebateCursorExpiredError,
  DebateStreamClient,
  SseFrameParser,
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
    canonicalMessages: [],
    drafts: {},
    lastSequence: 0,
    activeGenerationId: "generation-1",
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
  })).snapshot;

  assert.equal(snapshot.drafts["message-1"].content, "Grounded argument.");
  assert.equal(snapshot.canonicalMessages.length, 0);

  snapshot = reduceDebateEvent(snapshot, event(5, "turn.completed", {
    generation_id: "generation-1",
    message: message("Grounded argument."),
  })).snapshot;

  assert.deepEqual(snapshot.drafts, {});
  assert.equal(snapshot.canonicalMessages[0].message.content, "Grounded argument.");
  assert.equal(snapshot.canonicalMessages[0].citations[0].evidence_id, "news-1");
});


test("reducer rejects a missing event or provider delta", () => {
  const snapshot: DebateStreamSnapshot = {
    status: "live",
    canonicalMessages: [],
    drafts: {},
    lastSequence: 4,
    activeGenerationId: "generation-1",
    safeError: null,
  };

  assert.throws(() => reduceDebateEvent(snapshot, event(6, "turn.delta", {
    message_id: "message-1",
    generation_id: "generation-1",
    delta_index: 2,
    delta: "late",
  })));
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
