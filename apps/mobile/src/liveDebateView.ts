import type { DebateStreamSnapshot } from "./debateStream";
import { presentDebateEvidence } from "./evidencePresentation.ts";
import type { DebateEvidenceView } from "./evidencePresentation.ts";
import type { DebateMessageRecord } from "./types.ts";

export type DebateStatusTone = "neutral" | "active" | "success" | "warning" | "danger";

export type DebateStatusCopy = {
  label: string;
  detail: string;
  tone: DebateStatusTone;
};

export type DebateMessageSections = {
  argument: string;
  factsUsed: DebateEvidenceView[];
  interpretation: string | null;
  uncertainty: string | null;
  hasAuthoritativePresentation: boolean;
};

export function debateMessageSections(
  record: DebateMessageRecord,
): DebateMessageSections {
  const presentation = record.presentation;
  if (!presentation || !record.message.is_complete) {
    return {
      argument: record.message.content,
      factsUsed: [],
      interpretation: null,
      uncertainty: null,
      hasAuthoritativePresentation: false,
    };
  }
  return {
    argument: presentation.argument,
    factsUsed: presentation.facts_used.map(presentDebateEvidence),
    interpretation: presentation.interpretation,
    uncertainty: presentation.uncertainty,
    hasAuthoritativePresentation: true,
  };
}

export function debateStatusCopy(snapshot: DebateStreamSnapshot): DebateStatusCopy {
  if (snapshot.sessionStatus === "interrupted_awaiting_user") {
    return { label: "Stopped here", detail: "Your visible text is saved. No generation resumes automatically.", tone: "neutral" };
  }
  if (snapshot.sessionStatus === "cancel_requested") {
    return {
      label: "Cancelling",
      detail: "The active generation is invalidated; late output will be discarded.",
      tone: "warning",
    };
  }
  if (snapshot.sessionStatus === "cancelled" || snapshot.jobStatus === "cancelled") {
    return {
      label: "Cancelled",
      detail: "No further messages will be added to this session.",
      tone: "neutral",
    };
  }
  if (snapshot.sessionStatus === "failed" || snapshot.jobStatus === "failed") {
    return {
      label: "Failed safely",
      detail: "Completed messages were preserved. No partial message became canonical.",
      tone: "danger",
    };
  }
  if (snapshot.sessionStatus === "completed") {
    return {
      label: "Final",
      detail: "Round 2 and the final neutral Judge summary are durable.",
      tone: "success",
    };
  }
  if (snapshot.sessionStatus === "awaiting_user") {
    return {
      label: "Waiting for your question",
      detail: "Round 1 is complete. Ask about a point before deciding whether to continue to Round 2.",
      tone: "success",
    };
  }
  if (snapshot.jobStatus === "retry_scheduled") {
    const delay = snapshot.retryDelaySeconds === null
      ? "shortly"
      : `in ${snapshot.retryDelaySeconds}s`;
    return {
      label: "Retry",
      detail: `Attempt ${snapshot.jobAttemptCount} paused; the Worker will retry ${delay}.`,
      tone: "warning",
    };
  }
  if (snapshot.jobStatus === "running") {
    return {
      label: "Running",
      detail: `Worker attempt ${Math.max(1, snapshot.jobAttemptCount)} is streaming the active turn.`,
      tone: "active",
    };
  }
  if (snapshot.jobStatus === "queued") {
    return {
      label: "Queued",
      detail: "The request is durable and will start when a bounded Worker is available.",
      tone: "active",
    };
  }
  return {
    label: "Preparing Debate",
    detail: "Loading canonical Session and Job state.",
    tone: "neutral",
  };
}

export function canCancelDebate(snapshot: DebateStreamSnapshot): boolean {
  return snapshot.activeGenerationId !== null
    && snapshot.sessionStatus !== "cancel_requested"
    && (snapshot.jobStatus === "queued"
      || snapshot.jobStatus === "running"
      || snapshot.jobStatus === "retry_scheduled");
}

export function canChallengeDebate(snapshot: DebateStreamSnapshot): boolean {
  return snapshot.sessionStatus === "awaiting_user";
}
