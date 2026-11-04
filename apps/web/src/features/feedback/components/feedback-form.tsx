import { FormProvider } from "react-hook-form";
import { config } from "@/app/config/env";
import { useFeedbackForm } from "../hooks/use-feedback-form";
import { AttachmentPicker } from "./attachment-picker";
import { FeedbackDetailsFields } from "./feedback-details-fields";
import { FeedbackDialogs } from "./feedback-dialogs";
import { FeedbackErrorSummary } from "./feedback-error-summary";
import { FeedbackSection } from "./feedback-section";
import { FeedbackSidePanel } from "./feedback-side-panel";
import { FormActions } from "./form-actions";
import { OptionalContactFields } from "./optional-contact-fields";
import { SubmissionResult } from "./submission-result";
import { SubmissionStatus } from "./submission-status";

export function FeedbackForm() {
  const flow = useFeedbackForm();
  const { attachments, submission, form } = flow;
  const disabled = submission.isSubmitting || config.feedbackMode === "disabled";
  if (submission.receipt)
    return <SubmissionResult receipt={submission.receipt} onReset={() => flow.perform("reset")} />;
  return (
    <FormProvider {...form}>
      <div className="grid items-start gap-7 lg:grid-cols-[minmax(0,1fr)_290px] xl:gap-10">
        <form
          onSubmit={flow.onSubmit}
          noValidate
          className="min-w-0 space-y-6"
          aria-label="Send feedback"
        >
          <FeedbackErrorSummary />
          <fieldset disabled={disabled} className="min-w-0 space-y-6">
            <FeedbackSection
              number="01"
              title="Your feedback"
              description="A specific suggestion helps us understand what matters to you."
            >
              <FeedbackDetailsFields />
            </FeedbackSection>
            <FeedbackSection
              number="02"
              title="Add a little context"
              description="Screenshots or documents are welcome. Attachments are optional."
            >
              <AttachmentPicker
                items={attachments.items}
                errors={attachments.errors}
                disabled={disabled}
                onAdd={attachments.add}
                onRemove={attachments.remove}
              />
            </FeedbackSection>
            <FeedbackSection
              number="03"
              title="Keep in touch, if you’d like"
              description="You can send feedback without sharing your name, email or gender."
            >
              <OptionalContactFields />
            </FeedbackSection>
          </fieldset>
          <SubmissionStatus
            phase={submission.phase}
            progress={submission.progress}
            error={submission.error}
            hasAttachments={attachments.items.length > 0}
          />
          <FormActions flow={flow} />
        </form>
        <FeedbackSidePanel
          scenario={flow.scenario}
          onScenarioChange={flow.setScenario}
          disabled={submission.isSubmitting}
        />
      </div>
      <FeedbackDialogs flow={flow} />
    </FormProvider>
  );
}
