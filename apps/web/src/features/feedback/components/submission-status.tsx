import { AlertCircle, LoaderCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import type { FeedbackRequestError } from "../api/feedback.contract";

type Props = {
  phase: string;
  progress: number;
  error: FeedbackRequestError | null;
  hasAttachments: boolean;
};

export function SubmissionStatus({ phase, progress, error, hasAttachments }: Props) {
  return (
    <div className="space-y-3" aria-live="polite" aria-atomic="true">
      {error && phase === "error" && (
        <Alert variant="destructive">
          <AlertCircle className="size-4" />
          <AlertTitle>We couldn’t finish this submission</AlertTitle>
          <AlertDescription>{error.message}</AlertDescription>
        </Alert>
      )}
      {phase === "cancelled" && (
        <p className="text-sm text-muted-foreground">
          Submission cancelled. Your draft and selected files are still here.
        </p>
      )}
      {phase === "processing" && (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Simulated processing · files stay in your browser
          </p>
          <Progress value={progress} aria-label="Simulated attachment processing" />
        </div>
      )}
      {phase === "sending" && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <LoaderCircle
            className="size-4 animate-spin motion-reduce:animate-none"
            aria-hidden="true"
          />
          {hasAttachments
            ? "Processing complete. Waiting for the submission receipt…"
            : "Waiting for the submission receipt…"}
        </p>
      )}
    </div>
  );
}
