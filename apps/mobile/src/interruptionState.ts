import type { DebateDraft, DebateStreamSnapshot } from "./debateStream";
import type { DebateMessageRecord, DebateSessionStatus } from "./types";

const INTERRUPTIBLE_SESSION_STATUSES = new Set([
  "queued_round_1",
  "running_round_1",
  "queued_round_2",
  "running_round_2",
]);

const INTERRUPTIBLE_ROLES = new Set(["bull", "bear", "judge"]);

function stableHash(value: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(36);
}

/**
 * A retryable mutation keeps the same key for the same interruption input,
 * including after a screen is recreated while a response is in flight.
 */
export function interruptionIdempotencyKey(prefix: "interject" | "continue", identity: string): string {
  return `${prefix}_${stableHash(identity)}`;
}

export function isInterruptionJobPending(jobStatus: DebateStreamSnapshot["jobStatus"]): boolean {
  return jobStatus === "queued" || jobStatus === "running" || jobStatus === "retry_scheduled";
}

/**
 * Stop can be requested while a queued/running generation has not emitted a
 * visible draft yet. The server validates this generation under its session
 * lock through /interrupt-before-output.
 */
export function canStopBeforeOutput(snapshot: DebateStreamSnapshot): boolean {
  return snapshot.activeGenerationId !== null
    && INTERRUPTIBLE_SESSION_STATUSES.has(snapshot.sessionStatus || "")
    && !snapshot.canonicalMessages.some(({ message }) =>
      message.generation_id === snapshot.activeGenerationId
      && INTERRUPTIBLE_ROLES.has(message.role),
    );
}

export function canStopVisibleDraft(
  snapshot: DebateStreamSnapshot,
  draft: DebateDraft | undefined,
): boolean {
  return snapshot.activeGenerationId !== null
    && INTERRUPTIBLE_SESSION_STATUSES.has(snapshot.sessionStatus || "")
    && draft !== undefined
    && INTERRUPTIBLE_ROLES.has(draft.role)
    && draft.generationId === snapshot.activeGenerationId;
}

/**
 * Resolve the provider draft behind the currently rendered draft. React can
 * render a snapshot one frame before the reveal scheduler has synced it, so a
 * missing rendered draft must not make buffered provider text look like an
 * empty generation. A completed canonical message may also still be draining
 * through the scheduler; retaining the rendered draft preserves that exact
 * visible prefix for the interruption request.
 */
export function activeInterruptionDraft(
  snapshot: DebateStreamSnapshot,
  displayedDraft?: DebateDraft,
): DebateDraft | null {
  if (displayedDraft && INTERRUPTIBLE_ROLES.has(displayedDraft.role)
      && displayedDraft.generationId === snapshot.activeGenerationId) {
    const received = snapshot.drafts[displayedDraft.messageId];
    return received || displayedDraft;
  }
  return Object.values(snapshot.drafts).find((draft) =>
    draft.generationId === snapshot.activeGenerationId
    && INTERRUPTIBLE_ROLES.has(draft.role),
  ) || null;
}

/** A before-output request is valid only while the provider has no text. */
export function shouldStopBeforeOutput(
  snapshot: DebateStreamSnapshot,
  displayedDraft?: DebateDraft,
): boolean {
  if (!canStopBeforeOutput(snapshot)) return false;
  return (activeInterruptionDraft(snapshot, displayedDraft)?.content.length || 0) === 0;
}

/** End needs a fresh stream until the server reports a terminal session. */
export function shouldReconnectAfterInterruptionEnd(status: DebateSessionStatus): boolean {
  return status !== "cancelled" && status !== "completed" && status !== "failed";
}

export function findInterruptedMessage(records: DebateMessageRecord[]): DebateMessageRecord | null {
  return [...records].reverse().find((record) =>
    !record.message.is_complete
    && INTERRUPTIBLE_ROLES.has(record.message.role)
    && record.message.metadata.interrupted === true,
  ) || null;
}

/**
 * Interjection records belong to the post-Stop active generation. The frozen
 * message itself keeps the cancelled generation so the two identifiers must
 * remain distinct when constructing a Continue request.
 */
export function findInterjection(
  records: DebateMessageRecord[],
  interruptedMessageId: string,
  waitingGenerationId: string,
): DebateMessageRecord | null {
  return [...records].reverse().find((record) =>
    record.message.role === "user"
    && record.message.generation_id === waitingGenerationId
    && record.message.metadata.interjection === true
    && record.message.metadata.interrupted_message_id === interruptedMessageId,
  ) || null;
}
