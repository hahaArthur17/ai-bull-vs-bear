import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useTranscriptFollow } from "./use-transcript-follow";

describe("transcript reading position", () => {
  it("stops following while someone reads older messages and resumes explicitly", () => {
    const { result, rerender } = renderHook(({ count }) => useTranscriptFollow(count), {
      initialProps: { count: 1 },
    });
    const viewport = document.createElement("div");
    const scrollTo = vi.fn();
    Object.defineProperties(viewport, {
      scrollHeight: { value: 1000 },
      clientHeight: { value: 400 },
      scrollTo: { value: scrollTo },
    });
    viewport.scrollTop = 600;
    result.current.viewportRef.current = viewport;
    rerender({ count: 2 });
    expect(scrollTo).toHaveBeenCalledOnce();

    viewport.scrollTop = 150;
    act(() => result.current.onScroll());
    expect(result.current.following).toBe(false);
    rerender({ count: 3 });
    expect(scrollTo).toHaveBeenCalledOnce();

    act(() => result.current.jumpToLatest());
    expect(result.current.following).toBe(true);
    expect(scrollTo).toHaveBeenCalledTimes(2);
    expect(scrollTo).toHaveBeenLastCalledWith({ top: 1000, behavior: "smooth" });
  });
});
