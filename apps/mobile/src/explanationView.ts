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
    !record.message.is_complete
    || !selectedText
    || selectedText.length > 500
    || !record.message.content.includes(selectedText)
  ) {
    return null;
  }
  return selectedText;
}


export function defaultExplanationQuestion(term: string): string {
  return `What does "${term}" mean in this message?`;
}
