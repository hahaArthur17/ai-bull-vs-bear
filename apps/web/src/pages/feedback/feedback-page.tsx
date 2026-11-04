import { ArrowLeft, FlaskConical } from "lucide-react";
import { Link } from "react-router-dom";
import { config } from "@/app/config/env";
import { PageHeading } from "@/components/shared/status/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { FeedbackForm } from "@/features/feedback/components/feedback-form";

export function FeedbackPage() {
  return (
    <div className="page-content space-y-8">
      <Button asChild variant="ghost" size="sm" className="-ml-3 text-muted-foreground">
        <Link to="/user#feedback">
          <ArrowLeft className="size-4" />
          Back to user page
        </Link>
      </Button>
      <PageHeading
        eyebrow="Made better together"
        title="Help shape what’s next."
        description="A small idea, an unexpected issue, a better way to do things. We’d love to hear your perspective."
        actions={
          config.feedbackMode === "demo" ? (
            <Badge variant="outline" className="gap-1.5 px-3 py-1.5">
              <FlaskConical className="size-3.5" />
              Feedback demo
            </Badge>
          ) : undefined
        }
      />
      {config.feedbackMode === "demo" && (
        <div className="flex gap-3 rounded-xl border border-primary/15 bg-primary/4 px-4 py-3 text-xs leading-relaxed text-muted-foreground">
          <FlaskConical className="mt-0.5 size-4 shrink-0 text-primary" />
          <p>
            <span className="font-medium text-foreground">Explore the full experience.</span> Your
            feedback and files stay in this browser. Nothing is sent to the developer.
          </p>
        </div>
      )}
      <FeedbackForm />
    </div>
  );
}

export default FeedbackPage;
