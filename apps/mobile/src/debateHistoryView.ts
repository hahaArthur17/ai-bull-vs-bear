import type { DebateSessionSummary } from "./types";


export type DebateHistoryCopy = {
  label: string;
  detail: string;
};


export function debateHistoryCopy(session: DebateSessionSummary): DebateHistoryCopy {
  if (session.status === "completed" && session.final_judge_message_id) {
    return {
      label: "FINAL JUDGE READY",
      detail: "Round 2 is complete with a durable neutral summary.",
    };
  }
  if (session.status === "awaiting_user") {
    return {
      label: "WAITING FOR CHALLENGE",
      detail: "Round 1 is complete and the interim Judge is ready.",
    };
  }
  if (session.status === "failed") {
    return {
      label: "GENERATION FAILED SAFELY",
      detail: "Completed transcript messages remain available.",
    };
  }
  if (session.status === "cancelled") {
    return {
      label: "DEBATE CANCELLED",
      detail: "No further messages will be added to this session.",
    };
  }
  return {
    label: "DEBATE IN PROGRESS",
    detail: "Open the durable session to see its current transcript.",
  };
}
