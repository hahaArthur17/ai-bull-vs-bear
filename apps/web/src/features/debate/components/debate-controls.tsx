import { Pause, Play, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

type Props = {
  playing: boolean;
  complete: boolean;
  visibleCount: number;
  total: number;
  progress: number;
  onToggle: () => void;
  onRestart: () => void;
};

export function DebateControls(props: Props) {
  const label = props.playing
    ? "Pause replay"
    : props.visibleCount
      ? "Continue replay"
      : "Start replay";
  return (
    <div className="border-t bg-card px-5 py-4 sm:px-7">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button onClick={props.onToggle} disabled={props.complete} className="min-w-36">
            {props.playing ? <Pause size={16} /> : <Play size={16} />}
            {props.complete ? "Replay complete" : label}
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={props.onRestart}
            aria-label="Restart replay"
          >
            <RotateCcw size={16} />
          </Button>
        </div>
        <p className="text-xs tabular-nums text-muted-foreground" aria-live="polite">
          {props.visibleCount} of {props.total} perspectives
        </p>
      </div>
      <div
        role="progressbar"
        aria-label="Replay progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={props.progress}
        className="mt-4 h-1 overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300 motion-reduce:transition-none"
          style={{ width: `${props.progress}%` }}
        />
      </div>
    </div>
  );
}
