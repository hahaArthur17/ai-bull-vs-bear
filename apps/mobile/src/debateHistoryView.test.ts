import assert from "node:assert/strict";
import test from "node:test";

import { debateHistoryCopy } from "./debateHistoryView.ts";
import type { DebateSessionSummary } from "./types";


const baseSession: DebateSessionSummary = {
  id: "session-1",
  ticker: "AAPL",
  status: "completed",
  active_branch_id: "branch-1",
  active_generation_id: "generation-2",
  opening_side: "bull",
  created_at: "2026-08-29T00:00:00Z",
  updated_at: "2026-08-29T00:10:00Z",
};


test("History distinguishes the durable final Judge from interim and active sessions", () => {
  assert.deepEqual(
    debateHistoryCopy({ ...baseSession, final_judge_message_id: "judge-2" }),
    {
      label: "FINAL JUDGE",
      title: "Final neutral assessment is ready",
      detail: "Round 2 is complete. Its canonical transcript and final Judge remain available to review.",
      action: "Review final assessment",
      kind: "final",
    },
  );
  assert.deepEqual(
    debateHistoryCopy({ ...baseSession, status: "awaiting_user" }),
    {
      label: "INTERIM JUDGE",
      title: "Round 1 is ready for your challenge",
      detail: "The interim Judge has paused the Debate. You may ask one evidence-grounded follow-up before Round 2.",
      action: "Open interim assessment",
      kind: "interim",
    },
  );
  assert.deepEqual(
    debateHistoryCopy({ ...baseSession, status: "running_round_2" }),
    {
      label: "IN PROGRESS",
      title: "Canonical Debate is still running",
      detail: "Open the durable session to see its current transcript.",
      action: "Open live transcript",
      kind: "active",
    },
  );
});
