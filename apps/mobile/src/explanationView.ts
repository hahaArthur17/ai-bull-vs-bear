import type { DebateMessageRecord } from "./types";

export type ExplanationRequestGate = {
  start: () => number;
  invalidate: () => void;
  isCurrent: (requestId: number) => boolean;
};

export function createExplanationRequestGate(): ExplanationRequestGate {
  let currentRequestId = 0;
  return {
    start: () => {
      currentRequestId += 1;
      return currentRequestId;
    },
    invalidate: () => {
      currentRequestId += 1;
    },
    isCurrent: (requestId) => requestId === currentRequestId,
  };
}

export function exactExplanationTerm(
  record: DebateMessageRecord,
  term: string,
): string | null {
  const selectedText = term.trim();
  if (
    !isExplanationSource(record)
    || !selectedText
    || selectedText.length > 500
    || !record.message.content.includes(selectedText)
  ) {
    return null;
  }
  return selectedText;
}

/**
 * A durable interrupted prefix is explainable but never promoted to a complete
 * claim. Empty before-output anchors intentionally have no Explanation action.
 */
export function isExplanationSource(record: DebateMessageRecord): boolean {
  return record.message.is_complete || (
    record.message.metadata.interrupted === true
    && record.message.content.trim().length > 0
  );
}


export function defaultExplanationQuestion(term: string): string {
  return `What does "${term}" mean in this message?`;
}

export function defaultPointPassage(content: string, maxLength = 240): string {
  const normalized = content.trim();
  if (normalized.length <= maxLength) return normalized;
  const candidate = normalized.slice(0, maxLength);
  const lastSpace = candidate.lastIndexOf(" ");
  const end = lastSpace >= Math.floor(maxLength * 0.6) ? lastSpace : maxLength;
  return candidate.slice(0, end).trimEnd();
}
