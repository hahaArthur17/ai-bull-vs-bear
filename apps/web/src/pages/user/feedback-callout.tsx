import { ArrowUpRight, MessageSquare } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function FeedbackCallout() {
  return (
    <section
      id="feedback"
      aria-labelledby="feedback-heading"
      className="scroll-mt-24 rounded-2xl bg-primary px-6 py-8 text-primary-foreground sm:px-8"
    >
      <div className="flex flex-wrap items-center justify-between gap-6">
        <div className="max-w-xl">
          <MessageSquare className="mb-5 size-5 opacity-80" aria-hidden="true" />
          <p className="mb-3 text-[10px] font-medium uppercase tracking-[0.18em] opacity-70">
            Made better together
          </p>
          <h2 id="feedback-heading" className="font-editorial text-3xl leading-tight">
            Help improve this app.
          </h2>
          <p className="mt-3 text-sm leading-relaxed opacity-80">
            An idea, an unexpected issue, or something that could feel a little better. There is
            room for your perspective, too.
          </p>
        </div>
        <Button asChild variant="secondary" className="shrink-0">
          <Link to="/feedback">
            Send feedback
            <ArrowUpRight className="size-4" />
          </Link>
        </Button>
      </div>
    </section>
  );
}
