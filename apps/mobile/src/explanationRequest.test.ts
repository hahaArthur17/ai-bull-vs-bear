import assert from "node:assert/strict";
import test from "node:test";

import { serializeExplanationRequest } from "./explanationRequest.ts";


test("Explanation requests preserve exact selections while using the API contract names", () => {
  assert.deepEqual(
    serializeExplanationRequest({
      messageId: "message-1",
      selectedText: "moving average",
      question: "What does this mean here?",
    }),
    {
      message_id: "message-1",
      selected_text: "moving average",
      question: "What does this mean here?",
    },
  );
});
