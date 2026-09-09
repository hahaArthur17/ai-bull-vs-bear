import assert from "node:assert/strict";
import test from "node:test";

import { RevealScheduler, revealUnits } from "./revealScheduler.ts";
import type { DebateDraft } from "./debateStream.ts";
import type { DebateMessageRecord } from "./types.ts";

const draft = (content: string): DebateDraft => ({
  messageId: "bull-1",
  generationId: "generation-1",
  role: "bull",
  content,
  nextDeltaIndex: 1,
  citations: [],
});

const canonical = (content: string): DebateMessageRecord => ({
  message: {
    id: "bull-1", session_id: "session-1", branch_id: "branch-1", generation_id: "generation-1",
    sequence_number: 1, round_number: 1, exchange_number: 1, role: "bull", message_kind: "argument",
    content, confidence: "medium", signal_strength: "medium", terms: [], metadata: {}, is_complete: true,
    created_at: "2026-09-08T00:00:00Z",
  },
  citations: [], presentation: null,
});

test("reveal units preserve whitespace, English words, CJK graphemes, and a trailing partial word", () => {
  assert.deepEqual(revealUnits("AAPL gains ", false), ["AAPL", " ", "gains", " "]);
  assert.deepEqual(revealUnits("分析中", false), ["分", "析"]);
  assert.deepEqual(revealUnits("分析中", true), ["分", "析", "中"]);
  assert.deepEqual(revealUnits("final", true), ["final"]);
});

test("a completed provider record remains a temporary display until its reveal buffer drains", () => {
  const scheduler = new RevealScheduler();
  scheduler.sync([], { "bull-1": draft("Grounded ") });
  scheduler.advance();
  scheduler.advance();
  scheduler.sync([canonical("Grounded argument.")], {});
  assert.equal(scheduler.display().canonicalMessages.length, 0);
  assert.equal(scheduler.display().drafts[0].content, "Grounded ");
  while (scheduler.advance()) undefined;
  assert.equal(scheduler.display().canonicalMessages[0].message.content, "Grounded argument.");
});

test("only the first unsettled message becomes visible and historical messages load immediately", () => {
  const scheduler = new RevealScheduler();
  scheduler.sync([canonical("Saved transcript.")], {});
  assert.equal(scheduler.display().canonicalMessages.length, 1);
  scheduler.sync([canonical("Saved transcript.")], { "bear-2": {
    ...draft("Counterpoint "), messageId: "bear-2", role: "bear",
  } });
  assert.equal(scheduler.display().drafts[0].messageId, "bear-2");
});

test("show full and app lifecycle settlement preserve every received character", () => {
  const scheduler = new RevealScheduler();
  scheduler.sync([], { "bull-1": draft("One two three.") });
  scheduler.advance();
  scheduler.showFull("bull-1");
  assert.equal(scheduler.display().drafts[0].content, "One two three.");
  scheduler.sync([canonical("One two three.")], {});
  assert.equal(scheduler.display().canonicalMessages.length, 1);
});

test("show full exposes a received trailing English word without waiting for a boundary", () => {
  const scheduler = new RevealScheduler();
  scheduler.sync([], { "bull-1": draft("unfinished") });
  scheduler.showFull("bull-1");
  assert.equal(scheduler.display().drafts[0].content, "unfinished");
});

test("reconnect and saved-history syncs settle canonical text instead of replaying typing", () => {
  const scheduler = new RevealScheduler();
  scheduler.sync([], { "bull-1": draft("received ") });
  scheduler.advance();
  scheduler.sync([canonical("received canonical response.")], {}, { immediate: true });
  assert.equal(scheduler.display().canonicalMessages[0].message.content, "received canonical response.");
});


test("split emoji, combining marks and supplementary Han stay intact", () => {
  assert.deepEqual(revealUnits("👩‍", false), []);
  assert.deepEqual(revealUnits("👩‍💻 ", false), ["👩‍💻", " "]);
  assert.deepEqual(revealUnits("e\u0301 ", false), ["e\u0301", " "]);
  assert.deepEqual(revealUnits("𠀀中", true), ["𠀀", "中"]);
});

test("a long completed response accelerates gradually and cannot jump to full text", () => {
  const scheduler = new RevealScheduler();
  scheduler.sync([], {});
  scheduler.sync([canonical("中".repeat(4000))], {});
  scheduler.advance();
  assert.ok(scheduler.display().drafts[0].content.length <= 12);
  assert.equal(scheduler.display().canonicalMessages.length, 0);
  while (scheduler.advance()) undefined;
  assert.equal(scheduler.display().canonicalMessages[0].message.content.length, 4000);
});

test("later completed agents stay hidden behind the current display prefix", () => {
  const scheduler = new RevealScheduler();
  scheduler.sync([], { "bull-1": draft("Opening ") });
  const second = canonical("Reply.");
  second.message = { ...second.message, id: "bear-2", sequence_number: 2, role: "bear" };
  scheduler.sync([canonical("Opening argument."), second], {});
  assert.deepEqual(scheduler.display().canonicalMessages, []);
  assert.equal(scheduler.display().drafts.length, 1);
  scheduler.showFull("bull-1");
  assert.equal(scheduler.display().drafts[0].messageId, "bear-2");
});

test("scheduler keeps canonical sequence order and gives a durable completion precedence", () => {
  const scheduler = new RevealScheduler();
  const first = canonical("First saved response.");
  const second = canonical("Second saved response.");
  second.message = { ...second.message, id: "bear-2", sequence_number: 2, role: "bear" };

  scheduler.sync([second, first], {
    "bear-2": { ...draft("stale transient output"), messageId: "bear-2", role: "bear" },
  });

  assert.deepEqual(
    scheduler.display().canonicalMessages.map((record) => record.message.id),
    ["bull-1", "bear-2"],
  );
  assert.equal(scheduler.display().drafts.length, 0);
});

test("freeze retains rendered prefix through late output, reconnect and accessibility settlement", () => {
  const scheduler = new RevealScheduler();
  scheduler.sync([], { 'bull-1': draft('One two three ') });
  scheduler.advance();
  const rendered = scheduler.display();
  scheduler.advance(); // Timer may run between render and click.
  scheduler.freeze(rendered);
  scheduler.sync([canonical('One two three completed.')], {}, { immediate: true });
  scheduler.settleAll();
  scheduler.showFull('bull-1');
  assert.equal(scheduler.advance(), false);
  assert.deepEqual(scheduler.display(), rendered);
  scheduler.releaseFreeze();
  const stopped = canonical(rendered.drafts[0].content);
  stopped.message.is_complete = false;
  scheduler.sync([stopped], {}, { immediate: true });
  assert.equal(scheduler.display().canonicalMessages[0].message.content, rendered.drafts[0].content);
});
