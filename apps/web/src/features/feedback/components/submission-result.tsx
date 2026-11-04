import { CheckCircle2, ArrowLeft, RotateCcw } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { FeedbackReceipt } from "../api/feedback.contract";

export function SubmissionResult({
  receipt,
  onReset,
}: {
  receipt: FeedbackReceipt;
  onReset: () => void;
}) {
  const isDemo = receipt.mode === "demo";
  return (
    <Card className="mx-auto max-w-2xl border-primary/15 shadow-none">
      <CardContent className="px-6 py-12 text-center sm:px-12">
        <div className="mx-auto mb-6 flex size-16 items-center justify-center rounded-full bg-primary/8">
          <CheckCircle2 className="size-8 text-primary" />
        </div>
        <Badge variant="secondary">{isDemo ? "Demo submission" : "Feedback received"}</Badge>
        <h2 className="mt-4 font-serif text-3xl">
          {isDemo ? "You’ve completed the feedback demo." : "Thank you for sharing your thoughts."}
        </h2>
        <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
          {isDemo
            ? "Your feedback and attachments stayed in this browser. Nothing was sent to the developer or stored on a server."
            : "The server confirmed your feedback was received. Keep the reference below for your records."}
        </p>
        <dl className="my-7 rounded-lg bg-muted/50 p-4 text-xs">
          <dt className="text-muted-foreground">
            {isDemo ? "Demo reference" : "Feedback reference"}
          </dt>
          <dd className="mt-1 break-all font-mono">{receipt.id}</dd>
          <dt className="mt-3 text-muted-foreground">Attachments</dt>
          <dd className="mt-1">
            {receipt.attachmentCount} {isDemo ? "processed locally" : "received"}
          </dd>
        </dl>
        <div className="flex flex-wrap justify-center gap-3">
          <Button asChild variant="outline">
            <Link to="/user#feedback">
              <ArrowLeft className="size-4" />
              Back to user page
            </Link>
          </Button>
          <Button onClick={onReset}>
            <RotateCcw className="size-4" />
            Send another feedback
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
