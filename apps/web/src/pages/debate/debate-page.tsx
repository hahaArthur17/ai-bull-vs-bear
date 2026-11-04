import { ArrowLeft, ArrowUpRight, Scale } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { DebateExperience } from "@/features/debate/components/debate-experience";
import { useDebateRecord } from "@/features/debate/hooks/use-debate-record";

export function DebatePage() {
  const { sessionId = "demo-aapl" } = useParams();
  const [params] = useSearchParams();
  const ticker = params.get("ticker") ?? undefined;
  const debate = useDebateRecord(sessionId, ticker);

  return (
    <div className="page-content space-y-7">
      <header>
        <Link
          to={debate.data ? `/stocks/${debate.data.ticker}` : "/"}
          className="mb-5 inline-flex items-center gap-2 text-xs font-medium text-muted-foreground hover:text-primary"
        >
          <ArrowLeft size={14} /> Back to research
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-primary">
              The other side of the story
            </p>
            <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">
              A conversation, not a verdict.
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
              Explore the case for and against. Follow the evidence before reaching your own
              conclusion.
            </p>
          </div>
          <Badge
            variant="outline"
            className="gap-1.5 rounded-full bg-card px-3 py-1.5 text-xs font-normal"
          >
            <Scale size={13} /> Demo replay
          </Badge>
        </div>
      </header>
      {debate.isPending ? (
        <DebateLoading />
      ) : debate.isError ? (
        <DebateError onRetry={() => void debate.refetch()} />
      ) : (
        <DebateExperience key={debate.data.id} record={debate.data} />
      )}
    </div>
  );
}

function DebateLoading() {
  return (
    <div
      role="status"
      aria-label="Loading debate"
      className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]"
    >
      <Skeleton className="h-[540px] rounded-2xl" />
      <Skeleton className="h-72 rounded-2xl" />
    </div>
  );
}

function DebateError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="rounded-2xl border bg-card px-6 py-14 text-center">
      <h2 className="font-serif text-2xl">We couldn't open this conversation.</h2>
      <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">
        The session may no longer be available. Try again, or start a fresh demonstration from a
        stock's research page.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Button onClick={onRetry}>Try again</Button>
        <Button variant="outline" asChild>
          <Link to="/">
            Explore stocks <ArrowUpRight size={15} />
          </Link>
        </Button>
      </div>
    </div>
  );
}
