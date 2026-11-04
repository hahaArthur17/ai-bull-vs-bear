import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { useResearch } from "@/features/research/hooks";
import type { DebateRecord } from "@/lib/contracts/research";
import { useDebateReplay } from "../hooks/use-debate-replay";
import { useSaveReplay } from "../hooks/use-save-replay";
import { DebateControls } from "./debate-controls";
import { DebateEvidenceDialog } from "./debate-evidence-dialog";
import { DebateSummary } from "./debate-summary";
import { DebateTranscript } from "./debate-transcript";

export function DebateExperience({ record }: { record: DebateRecord }) {
  const replay = useDebateReplay(record.messages.length);
  const saved = useSaveReplay(record, replay.complete);
  const research = useResearch(record.ticker);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const evidence = research.data?.evidence.find((item) => item.id === evidenceId);

  return (
    <>
      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
        <section
          aria-label="Debate replay"
          className="min-w-0 overflow-hidden rounded-2xl border bg-card shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-4 sm:px-7">
            <div className="flex items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-lg bg-secondary text-xs font-bold text-primary">
                {record.ticker.slice(0, 2)}
              </span>
              <div>
                <h2 className="text-sm font-semibold">{record.ticker} · Perspective room</h2>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Bull, Bear & a considered synthesis
                </p>
              </div>
            </div>
            <Badge variant="outline" className="gap-1.5 rounded-full py-1 font-normal">
              <span
                className={`size-1.5 rounded-full ${replay.playing ? "bg-primary" : "bg-muted-foreground/60"}`}
              />
              {replay.complete
                ? "Complete"
                : replay.playing
                  ? "Playing"
                  : replay.visibleCount
                    ? "Paused"
                    : "Ready when you are"}
            </Badge>
          </div>
          <DebateTranscript
            key={replay.visibleCount ? record.id : "ready"}
            messages={record.messages.slice(0, replay.visibleCount)}
            onEvidence={setEvidenceId}
          />
          <DebateControls
            {...replay}
            total={record.messages.length}
            onToggle={replay.toggle}
            onRestart={replay.restart}
          />
        </section>
        <DebateSummary
          complete={replay.complete}
          summary={record.summary}
          saveStatus={saved.status}
          onRetry={saved.retry}
        />
      </div>
      <DebateEvidenceDialog
        evidence={evidence}
        loading={research.isPending}
        error={research.isError}
        onRetry={() => void research.refetch()}
        open={evidenceId !== null}
        onOpenChange={(open) => {
          if (!open) setEvidenceId(null);
        }}
      />
    </>
  );
}
