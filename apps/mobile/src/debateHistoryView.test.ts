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
      label: "FINAL JUDGE READY",
      detail: "Round 2 is complete with a durable neutral summary.",
    },
  );
  assert.deepEqual(
    debateHistoryCopy({ ...baseSession, status: "awaiting_user" }),
    {
      label: "WAITING FOR CHALLENGE",
      detail: "Round 1 is complete and the interim Judge is ready.",
    },
  );
  assert.deepEqual(
    debateHistoryCopy({ ...baseSession, status: "running_round_2" }),
    {
      label: "DEBATE IN PROGRESS",
      detail: "Open the durable session to see its current transcript.",
    },
  );
});
