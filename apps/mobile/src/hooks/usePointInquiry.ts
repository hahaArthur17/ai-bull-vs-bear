import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type RefObject,
  type SetStateAction,
} from "react";
import { api } from "../api";
import { createCanonicalDebateSnapshot, type DebateStreamSnapshot } from "../debateStream";
import {
  createExplanationRequestGate,
  defaultExplanationQuestion,
  defaultPointPassage,
  exactExplanationTerm,
} from "../explanationView";
import {
  canSubmitRoundTwoChallenge,
  INITIAL_POINT_INQUIRY_MODE,
  type PointInquiryMode,
} from "../pointInquiryView";
import type { DebateMessageRecord, DebateSessionDetail, ExplanationResult } from "../types";

function newIdempotencyKey(prefix: string): string {
  return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

/** Own the point dialog and ignore explanation/challenge responses after its context changes. */
export function usePointInquiry({
  sessionId,
  canChallenge,
  currentSessionId,
  setSnapshot,
  setStreamEpoch,
  setActionError,
}: {
  sessionId: string;
  canChallenge: boolean;
  currentSessionId: RefObject<string>;
  setSnapshot: Dispatch<SetStateAction<DebateStreamSnapshot>>;
  setStreamEpoch: Dispatch<SetStateAction<number>>;
  setActionError: Dispatch<SetStateAction<string>>;
}) {
  const [challenging, setChallenging] = useState(false);
  const [pointTarget, setPointTarget] = useState<DebateMessageRecord | null>(null);
  const [pointDialogMode, setPointDialogMode] = useState<PointInquiryMode>(
    INITIAL_POINT_INQUIRY_MODE,
  );
  const [selectedText, setSelectedText] = useState("");
  const [question, setQuestion] = useState("");
  const [explanationResult, setExplanationResult] = useState<ExplanationResult | null>(null);
  const [explanationError, setExplanationError] = useState("");
  const [explaining, setExplaining] = useState(false);
  const challengeKey = useRef<string | null>(null);
  const explanationRequests = useRef(createExplanationRequestGate());
  const challengeSubmissionInFlight = useRef<symbol | null>(null);
  const invalidateExplanationRequest = () => {
    explanationRequests.current.invalidate();
    setExplaining(false);
  };

  const selectedTextIsValid =
    pointTarget !== null &&
    selectedText.trim().length > 0 &&
    pointTarget.message.content.includes(selectedText.trim());
  const canSubmitChallenge = canSubmitRoundTwoChallenge({
    mode: pointDialogMode,
    canChallenge,
    selectedTextIsValid,
    question,
    challenging,
  });
  const selectedExplanationTerm = pointTarget
    ? exactExplanationTerm(pointTarget, selectedText)
    : null;
  const canSubmitExplanation =
    selectedExplanationTerm !== null && question.trim().length > 0 && !explaining;
  const openPointQuestion = (record: DebateMessageRecord) => {
    invalidateExplanationRequest();
    setPointTarget(record);
    setPointDialogMode(INITIAL_POINT_INQUIRY_MODE);
    setSelectedText(defaultPointPassage(record.message.content));
    setQuestion("");
    setExplanationResult(null);
    setExplanationError("");
    setActionError("");
    challengeKey.current = null;
  };

  const selectExplanationTerm = (record: DebateMessageRecord, term: string) => {
    const selectedTerm = exactExplanationTerm(record, term);
    if (selectedTerm === null) {
      setActionError("This term is not an exact selection from an explainable message.");
      return;
    }
    invalidateExplanationRequest();
    setPointTarget(record);
    setPointDialogMode(INITIAL_POINT_INQUIRY_MODE);
    setSelectedText(selectedTerm);
    setQuestion(defaultExplanationQuestion(selectedTerm));
    setExplanationResult(null);
    setExplanationError("");
  };

  const closePointDialog = () => {
    invalidateExplanationRequest();
    setPointTarget(null);
    setPointDialogMode(INITIAL_POINT_INQUIRY_MODE);
    setSelectedText("");
    setQuestion("");
    setExplanationResult(null);
    setExplanationError("");
    setActionError("");
    challengeKey.current = null;
  };

  const prepareRoundTwoChallenge = () => {
    invalidateExplanationRequest();
    setPointDialogMode("challenge");
    setExplanationError("");
    setActionError("");
  };

  const returnToExplanation = () => {
    setPointDialogMode("explain");
    challengeKey.current = null;
  };

  const submitChallenge = async () => {
    if (!pointTarget || !canSubmitChallenge || challengeSubmissionInFlight.current !== null) return;
    const submissionId = Symbol("round2-challenge");
    challengeSubmissionInFlight.current = submissionId;
    setChallenging(true);
    setActionError("");
    challengeKey.current ||= newIdempotencyKey("round2");
    const showAdmittedChallenge = (detail: DebateSessionDetail) => {
      setSnapshot(createCanonicalDebateSnapshot(detail));
      closePointDialog();
      setStreamEpoch((current) => current + 1);
    };
    try {
      const detail = await api.challengeDebate(sessionId, {
        selectedMessageId: pointTarget.message.id,
        selectedText: selectedText.trim(),
        question: question.trim(),
        idempotencyKey: challengeKey.current,
      });
      if (currentSessionId.current !== sessionId) return;
      showAdmittedChallenge(detail);
    } catch (error) {
      if (currentSessionId.current !== sessionId) return;
      // The durable challenge may have committed even if the response timed
      // out. Read the canonical session before offering another submission.
      try {
        const detail = await api.getDebate(sessionId);
        if (currentSessionId.current !== sessionId) return;
        if (
          detail.messages.some(
            (record) => record.message.round_number === 2 && record.message.role === "user",
          )
        ) {
          showAdmittedChallenge(detail);
          return;
        }
      } catch {
        // Keep the original mutation error when the recovery read also fails.
      }
      if (currentSessionId.current !== sessionId) return;
      setActionError(
        error instanceof Error ? error.message : "Could not start the second Debate round.",
      );
    } finally {
      if (challengeSubmissionInFlight.current === submissionId) {
        challengeSubmissionInFlight.current = null;
        setChallenging(false);
      }
    }
  };

  const submitExplanation = async () => {
    if (!pointTarget || !selectedExplanationTerm || !canSubmitExplanation) return;
    const requestId = explanationRequests.current.start();
    setExplaining(true);
    setExplanationError("");
    try {
      const result = await api.explainDebate(sessionId, {
        messageId: pointTarget.message.id,
        selectedText: selectedExplanationTerm,
        question: question.trim(),
      });
      if (explanationRequests.current.isCurrent(requestId)) {
        setExplanationResult(result);
      }
    } catch (error) {
      if (explanationRequests.current.isCurrent(requestId)) {
        setExplanationError(
          error instanceof Error ? error.message : "Could not explain this term.",
        );
      }
    } finally {
      if (explanationRequests.current.isCurrent(requestId)) {
        setExplaining(false);
      }
    }
  };

  useEffect(() => {
    closePointDialog();
    challengeSubmissionInFlight.current = null;
    setChallenging(false);
    return () => explanationRequests.current.invalidate();
  }, [sessionId]);

  return {
    pointTarget,
    pointDialogMode,
    selectedText,
    question,
    selectedTextIsValid,
    canSubmitChallenge,
    selectedExplanationTerm,
    canSubmitExplanation,
    challenging,
    explaining,
    explanationResult,
    explanationError,
    openPointQuestion,
    selectExplanationTerm,
    closePointDialog,
    prepareRoundTwoChallenge,
    returnToExplanation,
    submitChallenge,
    submitExplanation,
    invalidateExplanationRequest,
    setSelectedText,
    setQuestion,
    setExplanationResult,
    setExplanationError,
    challengeKey,
  };
}
