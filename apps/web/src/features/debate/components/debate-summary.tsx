import { Check, CheckCircle2, Copy, Scale } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type Props = {
  complete: boolean;
  summary: string;
  saveStatus: "idle" | "pending" | "success" | "error";
  onRetry: () => void;
};

async function copySummary(summary: string) {
  try {
    await navigator.clipboard.writeText(summary);
    toast.success("Summary copied");
  } catch {
    toast.error("Couldn't copy. You can select the summary text instead.");
  }
}

export function DebateSummary(props: Props) {
  return (
    <aside className="space-y-5">
      <Card className="border-primary/15 bg-primary/[0.035] shadow-none">
        <CardContent className="p-6">
          <Scale size={21} className="mb-4 text-primary" strokeWidth={1.5} />
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-primary">
            The bigger picture
          </p>
          <h2 className="mt-2 font-serif text-2xl">
            {props.complete ? "Both sides, considered." : "Keep an open thesis."}
          </h2>
          <p className="mt-4 text-sm leading-7 text-muted-foreground">
            {props.complete
              ? props.summary
              : "The strongest research makes room for uncertainty. Read each perspective, then inspect the evidence behind it."}
          </p>
          {props.complete && (
            <Button
              variant="outline"
              size="sm"
              className="mt-5 w-full bg-background"
              onClick={() => void copySummary(props.summary)}
            >
              <Copy size={14} /> Copy summary
            </Button>
          )}
        </CardContent>
      </Card>
      <div className="px-1">
        <h3 className="text-xs font-semibold uppercase tracking-[0.13em] text-muted-foreground">
          A note on this session
        </h3>
        <p className="mt-3 text-xs leading-6 text-muted-foreground">
          You're viewing a prepared demonstration. Perspectives and citations are illustrative, not
          a live AI response or investment advice.
        </p>
        {props.complete && <SaveStatus status={props.saveStatus} onRetry={props.onRetry} />}
      </div>
    </aside>
  );
}

function SaveStatus({ status, onRetry }: { status: Props["saveStatus"]; onRetry: () => void }) {
  if (status === "error")
    return (
      <div className="mt-4 text-xs">
        <p>Couldn't save this replay.</p>
        <Button variant="link" size="sm" onClick={onRetry}>
          Try saving again
        </Button>
      </div>
    );
  if (status !== "success")
    return (
      <p role="status" className="mt-4 text-xs text-muted-foreground">
        Saving to your history…
      </p>
    );
  return (
    <div className="mt-5 border-t pt-4">
      <p role="status" className="flex items-center gap-2 text-xs text-primary">
        <CheckCircle2 size={14} /> Saved to your history
      </p>
      <Button asChild variant="link" size="sm" className="mt-2 px-0">
        <Link to="/history">
          <Check size={13} /> View saved sessions
        </Link>
      </Button>
    </div>
  );
}
