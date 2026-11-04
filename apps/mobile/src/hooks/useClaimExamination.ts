import { useCallback, useEffect, useRef, useState } from "react";
import type { Claim, ExaminationResponse } from "../types";

type Question = ExaminationResponse["question_type"];

/** BB-004: bind each answer to the selected claim and dialog lifetime. */
export function useClaimExamination(
  examine: (claimId: string, question: Question) => Promise<ExaminationResponse>,
) {
  const [claim, setClaim] = useState<Claim | null>(null);
  const [result, setResult] = useState<ExaminationResponse | null>(null);
  const [error, setError] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState<Question | null>(null);
  const context = useRef(0);
  const inFlight = useRef(false);
  useEffect(
    () => () => {
      context.current += 1;
    },
    [],
  );

  const reset = useCallback(() => {
    context.current += 1;
    inFlight.current = false;
    setClaim(null);
    setResult(null);
    setError("");
    setPendingQuestion(null);
  }, []);

  const open = (next: Claim) => {
    reset();
    setClaim(next);
  };

  const ask = async (question: Question) => {
    if (!claim || inFlight.current) return;
    const requestContext = context.current;
    inFlight.current = true;
    setPendingQuestion(question);
    setError("");
    try {
      const answer = await examine(claim.id, question);
      if (context.current === requestContext) setResult(answer);
    } catch (failure) {
      if (context.current === requestContext)
        setError(failure instanceof Error ? failure.message : "Could not examine the claim.");
    } finally {
      if (context.current === requestContext) {
        inFlight.current = false;
        setPendingQuestion(null);
      }
    }
  };

  return { claim, result, error, pendingQuestion, open, reset, ask };
}
