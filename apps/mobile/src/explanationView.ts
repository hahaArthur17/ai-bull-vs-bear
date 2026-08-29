import type { DebateMessageRecord } from "./types";


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
