import type { FeedbackFlow } from "../hooks/use-feedback-form";
import { FormConfirmation } from "./form-confirmation";

export function FeedbackDialogs({ flow }: { flow: FeedbackFlow }) {
  const { blocker } = flow;
  return (
    <>
      <FormConfirmation
        open={flow.confirmation !== null}
        title={
          flow.confirmation === "sample" ? "Replace your current draft?" : "Clear this feedback?"
        }
        description="Your current text and selected files will be removed. This can’t be undone."
        action={flow.confirmation === "sample" ? "Use sample feedback" : "Reset form"}
        onConfirm={() => {
          if (flow.confirmation) flow.perform(flow.confirmation);
        }}
        onCancel={() => flow.setConfirmation(null)}
      />
      <FormConfirmation
        open={blocker.state === "blocked"}
        title="Leave this feedback behind?"
        description="Your unsent draft and selected files will be cleared when you leave."
        action="Leave page"
        onConfirm={() => blocker.proceed?.()}
        onCancel={() => blocker.reset?.()}
      />
    </>
  );
}
