import { useFormContext } from "react-hook-form";
import { AlertCircle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import type { FeedbackValues } from "../model/feedback.schema";

export function FeedbackErrorSummary() {
  const {
    formState: { errors, submitCount },
    setFocus,
  } = useFormContext<FeedbackValues>();
  const fields = Object.entries(errors);
  if (!submitCount || !fields.length) return null;
  return (
    <Alert variant="destructive" className="bg-background">
      <AlertCircle className="size-4" />
      <AlertTitle>A few details need your attention</AlertTitle>
      <AlertDescription>
        <ul className="mt-2 space-y-1">
          {fields.map(([name, error]) => (
            <li key={name}>
              <button
                type="button"
                className="text-left underline underline-offset-4"
                onClick={() => setFocus(name as keyof FeedbackValues)}
              >
                {error?.message?.toString()}
              </button>
            </li>
          ))}
        </ul>
      </AlertDescription>
    </Alert>
  );
}
