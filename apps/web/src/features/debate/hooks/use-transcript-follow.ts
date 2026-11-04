import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "./use-reduced-motion";

export function useTranscriptFollow(visibleCount: number) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const followingRef = useRef(true);
  const [following, setFollowing] = useState(true);
  const reduceMotion = useReducedMotion();

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport || !followingRef.current) return;
    viewport.scrollTo?.({
      top: viewport.scrollHeight,
      behavior: reduceMotion ? "instant" : "smooth",
    });
  }, [visibleCount, reduceMotion]);

  const onScroll = () => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const next = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 64;
    followingRef.current = next;
    setFollowing(next);
  };

  const jumpToLatest = () => {
    followingRef.current = true;
    setFollowing(true);
    const viewport = viewportRef.current;
    viewport?.scrollTo?.({
      top: viewport.scrollHeight,
      behavior: reduceMotion ? "instant" : "smooth",
    });
  };

  return { viewportRef, following, onScroll, jumpToLatest };
}
