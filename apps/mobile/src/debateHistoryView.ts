import type { DebateSessionSummary } from "./types";

const ACTIVE_DEBATE_CONFLICT_DETAIL = "Finish or cancel the active Debate before starting another";
const TERMINAL_DEBATE_STATUSES = new Set<DebateSessionSummary["status"]>([
  "completed",
  "cancelled",
  "failed",
]);


export type DebateHistoryCopy = {
  label: string;
  title: string;
  detail: string;
  action: string;
  kind: "final" | "interim" | "active" | "cancelled" | "failed";
};

export function isActiveDebateConflict(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  const responseError = error as Error & { detail?: unknown; status?: unknown };
  const detail = typeof responseError.detail === "string"
    ? responseError.detail
    : responseError.message;
  return responseError.status === 409 && detail === ACTIVE_DEBATE_CONFLICT_DETAIL;
}

export function findActiveDebate(
  sessions: DebateSessionSummary[],
): DebateSessionSummary | null {
  return sessions.find((session) => !TERMINAL_DEBATE_STATUSES.has(session.status)) ?? null;
}


export function debateHistoryCopy(session: DebateSessionSummary): DebateHistoryCopy {
  if (session.status === "completed" && session.final_judge_message_id) {
    return {
      label: "FINAL JUDGE",
      title: "Final neutral assessment is ready",
      detail: "Round 2 is complete. Its canonical transcript and final Judge remain available to review.",
      action: "Review final assessment",
      kind: "final",
    };
  }
  if (session.status === "awaiting_user") {
    return {
      label: "INTERIM JUDGE",
      title: "Round 1 is ready for your question",
      detail: "The interim Judge has paused the Debate. Ask for an explanation, then decide whether to continue to Round 2.",
      action: "Open interim assessment",
      kind: "interim",
    };
  }
  if (session.status === "failed") {
    return {
      label: "SAFE FAILURE",
      title: "Generation stopped safely",
      detail: "Completed transcript messages remain available.",
      action: "Review saved transcript",
      kind: "failed",
    };
  }
  if (session.status === "cancelled") {
    return {
      label: "CANCELLED",
      title: "This Debate was cancelled",
      detail: "No further messages will be added to this session.",
      action: "Review saved transcript",
      kind: "cancelled",
    };
  }
  return {
    label: "IN PROGRESS",
    title: "Canonical Debate is still running",
    detail: "Open the durable session to see its current transcript.",
    action: "Open live transcript",
    kind: "active",
  };
}
