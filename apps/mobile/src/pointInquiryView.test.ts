import assert from "node:assert/strict";
import test from "node:test";

import {
  canDismissPointInquiry,
  canPrepareRoundTwoChallenge,
  canSubmitRoundTwoChallenge,
  INITIAL_POINT_INQUIRY_MODE,
} from "./pointInquiryView.ts";

test("asking about a point defaults to read-only explanation", () => {
  assert.equal(INITIAL_POINT_INQUIRY_MODE, "explain");
});

test("Round 2 preparation requires an explicit valid question at the interim pause", () => {
  const valid = {
    canChallenge: true,
    selectedTextIsValid: true,
    question: "Which evidence should both sides reconsider?",
    explaining: false,
  };
  assert.equal(canPrepareRoundTwoChallenge(valid), true);
  assert.equal(canPrepareRoundTwoChallenge({ ...valid, canChallenge: false }), false);
  assert.equal(canPrepareRoundTwoChallenge({ ...valid, selectedTextIsValid: false }), false);
  assert.equal(canPrepareRoundTwoChallenge({ ...valid, question: "   " }), false);
  assert.equal(canPrepareRoundTwoChallenge({ ...valid, explaining: true }), false);
});

test("Round 2 submission stays impossible until the explicit confirmation mode", () => {
  const validInput = {
    canChallenge: true,
    selectedTextIsValid: true,
    question: "Which evidence changes this interpretation?",
    challenging: false,
  };

  assert.equal(canSubmitRoundTwoChallenge({ mode: "explain", ...validInput }), false);
  assert.equal(canSubmitRoundTwoChallenge({ mode: "challenge", ...validInput }), true);
});

test("the dialog dismisses normally but stays open while Round 2 is being committed", () => {
  assert.equal(canDismissPointInquiry(false), true);
  assert.equal(canDismissPointInquiry(true), false);
});
