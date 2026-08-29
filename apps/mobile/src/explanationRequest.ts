import type { ExplanationRequest } from "./types";


export function serializeExplanationRequest(request: ExplanationRequest) {
  return {
    message_id: request.messageId,
    selected_text: request.selectedText,
    question: request.question,
  };
}
