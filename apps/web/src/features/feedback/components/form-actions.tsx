import { ArrowUpRight, RotateCcw, Sparkles } from "lucide-react";
import { config } from "@/app/config/env";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import type { FeedbackFlow } from "../hooks/use-feedback-form";

export function FormActions({ flow }: { flow: FeedbackFlow }) {
  const { submission } = flow;
  const disabled = submission.isSubmitting || config.feedbackMode === "disabled";
  return (
    <>
      {config.feedbackMode === "disabled" && (
        <Alert>
          <AlertDescription>
            Feedback submission is not connected yet. Please check back later.
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-6">
        <Button
          type="button"
          variant="ghost"
          disabled={submission.isSubmitting}
          onClick={() => flow.requestAction("reset")}
        >
          <RotateCcw className="size-4" />
          Reset form
        </Button>
        <div className="flex flex-wrap gap-2">
          {config.feedbackMode === "demo" && (
            <Button
              type="button"
              variant="outline"
              disabled={disabled}
              onClick={() => flow.requestAction("sample")}
            >
              <Sparkles className="size-4" />
              Fill sample feedback
            </Button>
          )}
          {submission.isSubmitting ? (
            <Button type="button" variant="outline" onClick={submission.cancel}>
              Cancel submission
            </Button>
          ) : (
            <Button type="submit" disabled={disabled}>
              {submission.phase === "error"
                ? "Retry submission"
                : config.feedbackMode === "demo"
                  ? "Try demo submission"
                  : "Send feedback"}
              <ArrowUpRight className="size-4" />
            </Button>
          )}
        </div>
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">
        {config.feedbackMode === "demo"
          ? "This is an interactive demo. No feedback or attachments are sent to the developer. Your draft clears when you leave or refresh."
          : config.feedbackMode === "disabled"
            ? "Submission is currently disabled. Nothing will be sent."
            : "Feedback is sent to the configured receiver. Optional contact details are only needed if you want a reply."}
      </p>
    </>
  );
}
