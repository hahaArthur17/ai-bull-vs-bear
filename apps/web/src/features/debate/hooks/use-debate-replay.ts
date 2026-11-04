import { useEffect, useState } from "react";
import { useReducedMotion } from "./use-reduced-motion";

export function useDebateReplay(total: number) {
  const [visibleCount, setVisibleCount] = useState(0);
  const [requestedPlaying, setRequestedPlaying] = useState(false);
  const reduceMotion = useReducedMotion();
  const complete = total > 0 && visibleCount >= total;
  const playing = requestedPlaying && !complete;

  useEffect(() => {
    if (!playing) return;
    const timer = window.setTimeout(
      () => setVisibleCount((count) => (reduceMotion ? total : Math.min(count + 1, total))),
      reduceMotion ? 0 : 1250,
    );
    return () => window.clearTimeout(timer);
  }, [playing, visibleCount, total, reduceMotion]);

  const restart = () => {
    setVisibleCount(0);
    setRequestedPlaying(false);
  };

  return {
    visibleCount,
    complete,
    playing,
    progress: total ? Math.round((visibleCount / total) * 100) : 0,
    toggle: () => setRequestedPlaying((value) => !value),
    restart,
  };
}
