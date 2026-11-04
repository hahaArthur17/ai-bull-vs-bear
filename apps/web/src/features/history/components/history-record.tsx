import { ArrowUpRight, Clock3, MessagesSquare, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DebateRecord } from "@/lib/contracts/research";

function displayDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Saved session"
    : new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(
        date,
      );
}

export function HistoryRecord({
  record,
  canDelete,
  onDelete,
}: {
  record: DebateRecord;
  canDelete: boolean;
  onDelete: (record: DebateRecord) => void;
}) {
  return (
    <article className="group flex items-center gap-2 rounded-2xl border bg-card pr-3 transition-colors hover:border-primary/30 sm:pr-5">
      <Link
        to={`/debates/${encodeURIComponent(record.id)}`}
        className="flex min-w-0 flex-1 gap-4 rounded-2xl p-5 focus-visible:outline-2 focus-visible:outline-primary sm:gap-5 sm:p-6"
        aria-label={`Reopen ${record.title}`}
      >
        <div className="hidden size-12 shrink-0 items-center justify-center rounded-xl border bg-secondary/50 text-xs font-bold text-primary sm:flex">
          {record.ticker.slice(0, 2)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="text-[10px] font-semibold">
              {record.ticker}
            </Badge>
            <span className="text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
              Demo session
            </span>
          </div>
          <h2 className="flex items-start gap-2 text-base font-semibold leading-6">
            {record.title}
            <ArrowUpRight
              size={15}
              className="mt-1 shrink-0 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 motion-reduce:transform-none"
            />
          </h2>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted-foreground">
            {record.summary}
          </p>
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1.5">
              <Clock3 size={12} />
              {displayDate(record.createdAt)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <MessagesSquare size={12} />
              {record.messages.length} perspectives
            </span>
          </div>
        </div>
      </Link>
      <Button
        variant="ghost"
        size="icon"
        className="shrink-0 text-muted-foreground hover:text-destructive"
        disabled={!canDelete}
        aria-label={`Delete ${record.title}`}
        title={canDelete ? "Delete saved session" : "These records are read-only"}
        onClick={() => onDelete(record)}
      >
        <Trash2 size={16} />
      </Button>
    </article>
  );
}
