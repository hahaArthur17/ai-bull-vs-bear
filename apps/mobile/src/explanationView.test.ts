import assert from "node:assert/strict";
import test from "node:test";

import {
  createExplanationRequestGate,
  defaultExplanationQuestion,
  exactExplanationTerm,
} from "./explanationView.ts";
import type { DebateMessageRecord } from "./types";


const message: DebateMessageRecord = {
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
    content: "The moving average supports a bounded bullish interpretation.",
    terms: ["moving average", "invented term"],
    metadata: {},
    is_complete: true,
    created_at: "2026-08-29T00:00:00Z",
  },
  citations: [],
};


test("Explanation terms must be exact selections from complete messages", () => {
  assert.equal(exactExplanationTerm(message, " moving average "), "moving average");
  assert.equal(exactExplanationTerm(message, "invented term"), null);
  assert.equal(
    exactExplanationTerm(
      { ...message, message: { ...message.message, is_complete: false } },
      "moving average",
    ),
    null,
  );
  assert.equal(
    defaultExplanationQuestion("moving average"),
    "What does \"moving average\" mean in this message?",
  );
});

test("Explanation requests become stale when the panel context changes", () => {
  const gate = createExplanationRequestGate();
  const firstRequest = gate.start();

  gate.invalidate(); // The user selected another term, edited the question, or closed the panel.
  assert.equal(gate.isCurrent(firstRequest), false);

  const secondRequest = gate.start();
  assert.equal(gate.isCurrent(firstRequest), false);
  assert.equal(gate.isCurrent(secondRequest), true);
});
