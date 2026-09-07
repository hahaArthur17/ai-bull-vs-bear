import assert from "node:assert/strict";
import test from "node:test";

import {
  debatePhaseBadge,
  getDebateChatLayout,
  getDebateMessagePlacement,
  shouldAutoFollowTranscript,
} from "./debateChatView.ts";

test("Debate chat layout stays readable at the four review widths", () => {
  assert.deepEqual(getDebateChatLayout(320), {
    bubbleWidth: "92%",
    judgeWidth: "96%",
    pagePadding: 14,
    showStatusRail: false,
  });
  assert.deepEqual(getDebateChatLayout(390), {
    bubbleWidth: "84%",
    judgeWidth: "88%",
    pagePadding: 18,
    showStatusRail: false,
  });
  assert.equal(getDebateChatLayout(768).bubbleWidth, "72%");
  assert.equal(getDebateChatLayout(768).showStatusRail, false);
  assert.equal(getDebateChatLayout(1280).bubbleWidth, "68%");
  assert.equal(getDebateChatLayout(1280).showStatusRail, true);
});

test("Debate phase badge describes the user-visible phase instead of transport closure", () => {
  assert.equal(debatePhaseBadge("awaiting_user", "closed"), "ROUND 1 PAUSED");
  assert.equal(debatePhaseBadge("completed", "closed"), "FINAL");
  assert.equal(debatePhaseBadge("running_round_2", "live"), "ROUND 2 LIVE");
  assert.equal(debatePhaseBadge(null, "reconnecting"), "RECONNECTING");
});

test("role placement conveys identity and Judge finality without color", () => {
  assert.deepEqual(getDebateMessagePlacement("bull", 1), {
    alignment: "left",
    kind: "bull",
    label: "Bull agent",
  });
  assert.equal(getDebateMessagePlacement("bear", 1).alignment, "right");
  assert.equal(getDebateMessagePlacement("user", 2).alignment, "center");
  assert.equal(getDebateMessagePlacement("judge", 1).label, "Interim neutral Judge");
  assert.equal(getDebateMessagePlacement("judge", 2).label, "Final neutral Judge");
});

test("transcript follows only while the reader remains near its end", () => {
  assert.equal(shouldAutoFollowTranscript(500, 600, 0), true);
  assert.equal(shouldAutoFollowTranscript(1200, 600, 520), true);
  assert.equal(shouldAutoFollowTranscript(1200, 600, 300), false);
  assert.equal(shouldAutoFollowTranscript(1200, 600, 504, 96), true);
});
