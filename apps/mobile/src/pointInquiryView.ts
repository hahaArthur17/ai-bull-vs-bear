export type PointInquiryMode = "explain" | "challenge";

export const INITIAL_POINT_INQUIRY_MODE: PointInquiryMode = "explain";

export function canDismissPointInquiry(challenging: boolean): boolean {
  return !challenging;
}

export function canPrepareRoundTwoChallenge({
  canChallenge,
  selectedTextIsValid,
  question,
  explaining,
}: {
  canChallenge: boolean;
  selectedTextIsValid: boolean;
  question: string;
  explaining: boolean;
}): boolean {
  return canChallenge
    && selectedTextIsValid
    && question.trim().length > 0
    && !explaining;
}

export function canSubmitRoundTwoChallenge({
  mode,
  canChallenge,
  selectedTextIsValid,
  question,
  challenging,
}: {
  mode: PointInquiryMode;
  canChallenge: boolean;
  selectedTextIsValid: boolean;
  question: string;
  challenging: boolean;
}): boolean {
  return mode === "challenge"
    && canChallenge
    && selectedTextIsValid
    && question.trim().length > 0
    && !challenging;
}
