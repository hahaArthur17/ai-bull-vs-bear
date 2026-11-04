import { useEffect, useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import type { DemoScenario } from "../api/feedback.contract";
import { defaultFeedback, feedbackSchema } from "../model/feedback.schema";
import type { FeedbackValues } from "../model/feedback.schema";
import { sampleFeedback } from "../model/sample-feedback";
import { useAttachmentQueue } from "./use-attachment-queue";
import { useDraftNavigation } from "./use-draft-navigation";
import { useFeedbackSubmission } from "./use-feedback-submission";

type FormAction = "reset" | "sample";

export function useFeedbackForm() {
  const form = useForm<FeedbackValues>({
    resolver: zodResolver(feedbackSchema),
    defaultValues: defaultFeedback,
    mode: "onBlur",
    reValidateMode: "onChange",
    shouldFocusError: true,
  });
  const attachments = useAttachmentQueue();
  const submission = useFeedbackSubmission();
  const [scenario, setScenario] = useState<DemoScenario>("normal");
  const [confirmation, setConfirmation] = useState<FormAction | null>(null);
  const dirty = !submission.receipt && (form.formState.isDirty || attachments.items.length > 0);
  const blocker = useDraftNavigation(Boolean(dirty));
  const { setError } = form;
  useEffect(() => {
    for (const [name, message] of Object.entries(submission.error?.fieldErrors ?? {})) {
      setError(name as keyof FeedbackValues, { type: "server", message }, { shouldFocus: true });
    }
  }, [submission.error, setError]);
  const clearAttachments = attachments.reset;
  useEffect(() => {
    if (submission.receipt) clearAttachments();
  }, [submission.receipt, clearAttachments]);
  const perform = (action: FormAction) => {
    submission.reset();
    attachments.reset();
    form.reset(action === "sample" ? sampleFeedback : defaultFeedback, { keepDefaultValues: true });
    setConfirmation(null);
  };
  const requestAction = (action: FormAction) => {
    if (dirty) setConfirmation(action);
    else perform(action);
  };
  const onSubmit = form.handleSubmit((values) =>
    submission.submit(
      values,
      attachments.items.map((item) => item.file),
      scenario,
    ),
  );
  return {
    form,
    attachments,
    submission,
    scenario,
    setScenario,
    confirmation,
    setConfirmation,
    perform,
    requestAction,
    blocker,
    onSubmit,
  };
}

export type FeedbackFlow = ReturnType<typeof useFeedbackForm>;
