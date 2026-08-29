import assert from "node:assert/strict";
import test from "node:test";

import { canSubmitExamination } from "./examinationState.ts";

test("a pending examination request disables every follow-up submission", () => {
  assert.equal(canSubmitExamination(null), true);
  assert.equal(canSubmitExamination("evidence_support"), false);
  assert.equal(canSubmitExamination("risk_meaning"), false);
});
