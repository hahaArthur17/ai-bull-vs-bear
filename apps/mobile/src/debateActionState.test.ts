import assert from "node:assert/strict";
import test from "node:test";

import { debateActionStatus } from "./debateActionState.ts";

test("debate action status makes cancellation, challenge, and read-only explanation distinct", () => {
  assert.equal(debateActionStatus({ cancelling: false, challenging: false, explaining: false }), null);
  assert.equal(debateActionStatus({ cancelling: false, challenging: false, explaining: true })?.label, "Explaining");
  assert.equal(debateActionStatus({ cancelling: false, challenging: true, explaining: true })?.label, "Queueing challenge");
  assert.equal(debateActionStatus({ cancelling: true, challenging: true, explaining: true })?.label, "Cancelling");
});
