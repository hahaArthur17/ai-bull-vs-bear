import { useMemo, useState } from "react";
import { BookOpen, RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import config from "@/app/config/env";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { HistoryDeleteDialog } from "@/features/history/components/history-delete-dialog";
import { HistoryEmpty } from "@/features/history/components/history-empty";
import { HistoryFilters } from "@/features/history/components/history-filters";
import { HistoryRecord } from "@/features/history/components/history-record";
import { useDeleteHistory, useHistory } from "@/features/history/hooks/use-history";
import type { DebateRecord } from "@/lib/contracts/research";

const emptyRecords: DebateRecord[] = [];

export function HistoryPage() {
  if (config.dataMode !== "demo") return <HistoryUnavailable />;
  return <DemoHistoryPage />;
}

function DemoHistoryPage() {
  const history = useHistory();
  const deletion = useDeleteHistory();
  const [query, setQuery] = useState("");
  const [ticker, setTicker] = useState("all");
  const [selected, setSelected] = useState<DebateRecord | null>(null);
  const records = history.data ?? emptyRecords;
  const tickers = [...new Set(records.map((record) => record.ticker))].sort();
  const visible = useMemo(() => filterRecords(records, query, ticker), [records, query, ticker]);
  const resetFilters = () => {
    setQuery("");
    setTicker("all");
  };
  const removeSelected = () => {
    if (!selected || config.dataMode !== "demo") return;
    deletion.mutate(selected.id, {
      onSuccess: () => {
        setSelected(null);
        toast.success("Session removed from history");
      },
      onError: () => toast.error("Couldn't remove this session. Please try again."),
    });
  };

  return (
    <div className="space-y-7">
      <HistoryHeading count={records.length} />
      <HistoryFilters
        query={query}
        ticker={ticker}
        tickers={tickers}
        onQuery={setQuery}
        onTicker={setTicker}
      />
      {history.isPending ? (
        <div role="status" aria-label="Loading saved sessions" className="space-y-4">
          {[1, 2, 3].map((id) => (
            <Skeleton key={id} className="h-44 rounded-2xl" />
          ))}
        </div>
      ) : history.isError ? (
        <HistoryError onRetry={() => void history.refetch()} />
      ) : visible.length ? (
        <div className="space-y-4">
          {visible.map((record) => (
            <HistoryRecord
              key={record.id}
              record={record}
              canDelete={config.dataMode === "demo" && !deletion.isPending}
              onDelete={setSelected}
            />
          ))}
        </div>
      ) : (
        <HistoryEmpty filtered={Boolean(query.trim()) || ticker !== "all"} onReset={resetFilters} />
      )}
      <HistoryDeleteDialog
        record={selected}
        pending={deletion.isPending}
        onCancel={() => setSelected(null)}
        onConfirm={removeSelected}
      />
    </div>
  );
}

function filterRecords(records: DebateRecord[], query: string, ticker: string) {
  const term = query.trim().toLowerCase();
  return records
    .filter(
      (record) =>
        (ticker === "all" || record.ticker === ticker) &&
        `${record.ticker} ${record.title} ${record.summary}`.toLowerCase().includes(term),
    )
    .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
}

function HistoryHeading({ count }: { count: number }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-primary">
          A record of your curiosity
        </p>
        <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">Research, revisited.</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Return to a perspective. Pick up a thread. Keep your thinking in view.
        </p>
      </div>
      <span className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1.5 text-xs text-muted-foreground">
        <BookOpen size={13} />
        {count} saved {count === 1 ? "session" : "sessions"}
      </span>
    </header>
  );
}

function HistoryError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="rounded-2xl border bg-card px-6 py-12 text-center">
      <h2 className="font-serif text-2xl">Your history couldn't be loaded.</h2>
      <p className="mt-3 text-sm text-muted-foreground">
        Your saved sessions may still be there. Try loading them again.
      </p>
      <Button variant="outline" onClick={onRetry} className="mt-5">
        <RefreshCw size={15} /> Try again
      </Button>
    </div>
  );
}

function HistoryUnavailable() {
  return (
    <div className="rounded-2xl border bg-card px-6 py-16 text-center">
      <BookOpen size={28} className="mx-auto mb-5 text-primary" strokeWidth={1.5} />
      <h1 className="font-serif text-3xl">A place to return to.</h1>
      <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-muted-foreground">
        Saved research sessions aren't available in this experience yet. You can keep exploring
        stocks and their evidence.
      </p>
      <Button asChild className="mt-6">
        <Link to="/">Back to research</Link>
      </Button>
    </div>
  );
}
