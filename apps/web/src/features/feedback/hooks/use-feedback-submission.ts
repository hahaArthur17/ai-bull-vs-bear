import { useEffect, useRef, useState } from "react";
import { config } from "@/app/config/env";
import { FeedbackRequestError } from "../api/feedback.contract";
import type { DemoScenario, FeedbackReceipt } from "../api/feedback.contract";
import { submitFeedback } from "../api/feedback.service";
import { toFeedbackPayload } from "../api/feedback.mapper";
import { fileIdentity } from "../model/attachment-policy";
import type { FeedbackValues } from "../model/feedback.schema";
import { simulateTransfer } from "../model/simulated-transfer";

type Phase = "idle" | "processing" | "sending" | "success" | "error" | "cancelled";
type Submission = {
  phase: Phase;
  progress: number;
  error: FeedbackRequestError | null;
  receipt: FeedbackReceipt | null;
};
const initial: Submission = { phase: "idle", progress: 0, error: null, receipt: null };

export function useFeedbackSubmission() {
  const [state, setState] = useState<Submission>(initial);
  const active = useRef<{ epoch: number; controller: AbortController | null; running: boolean }>({
    epoch: 0,
    controller: null,
    running: false,
  });
  const retryKey = useRef({ fingerprint: "", key: "" });
  useEffect(
    () => () => {
      active.current.epoch++;
      active.current.controller?.abort();
    },
    [],
  );
  const cancel = () => {
    active.current.epoch++;
    active.current.controller?.abort();
    active.current.running = false;
    setState((current) => ({ ...current, phase: "cancelled", error: null }));
  };
  const reset = () => {
    active.current.epoch++;
    active.current.controller?.abort();
    active.current.running = false;
    retryKey.current = { fingerprint: "", key: "" };
    setState(initial);
  };
  const submit = async (values: FeedbackValues, files: File[], scenario: DemoScenario) => {
    if (active.current.running) return;
    const controller = new AbortController();
    const epoch = ++active.current.epoch;
    active.current.controller = controller;
    active.current.running = true;
    const isCurrent = () => active.current.epoch === epoch;
    const fingerprint = JSON.stringify([toFeedbackPayload(values), files.map(fileIdentity)]);
    if (retryKey.current.fingerprint !== fingerprint)
      retryKey.current = { fingerprint, key: crypto.randomUUID() };
    setState({
      ...initial,
      phase: files.length && config.feedbackMode === "demo" ? "processing" : "sending",
    });
    try {
      if (files.length && config.feedbackMode === "demo") {
        await simulateTransfer(controller.signal, (progress) => {
          if (isCurrent()) setState((current) => ({ ...current, progress }));
        });
      }
      if (!isCurrent()) return;
      setState((current) => ({ ...current, phase: "sending" }));
      const receipt = await submitFeedback(values, files, {
        signal: controller.signal,
        idempotencyKey: retryKey.current.key,
        scenario,
      });
      if (isCurrent()) setState({ phase: "success", receipt, error: null, progress: 100 });
    } catch (error) {
      if (isCurrent())
        setState((current) => ({
          ...current,
          phase: controller.signal.aborted ? "cancelled" : "error",
          error:
            error instanceof FeedbackRequestError
              ? error
              : new FeedbackRequestError("Something went wrong. Your draft is still here."),
        }));
    } finally {
      if (isCurrent()) active.current.running = false;
    }
  };
  return {
    ...state,
    isSubmitting: state.phase === "processing" || state.phase === "sending",
    submit,
    cancel,
    reset,
  };
}
