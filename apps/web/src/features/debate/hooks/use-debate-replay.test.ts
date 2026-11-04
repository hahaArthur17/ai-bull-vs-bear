import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useDebateReplay } from "./use-debate-replay";

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("debate replay", () => {
  it("pauses without advancing and resumes to a bounded completion", () => {
    const { result } = renderHook(() => useDebateReplay(2));
    expect(result.current.visibleCount).toBe(0);
    act(() => result.current.toggle());
    act(() => vi.advanceTimersByTime(1250));
    expect(result.current.visibleCount).toBe(1);
    act(() => result.current.toggle());
    act(() => vi.advanceTimersByTime(5000));
    expect(result.current.visibleCount).toBe(1);
    act(() => result.current.toggle());
    act(() => vi.advanceTimersByTime(1250));
    expect(result.current.complete).toBe(true);
    expect(result.current.playing).toBe(false);
    expect(result.current.progress).toBe(100);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("restarts from a clean, paused state and clears work on unmount", () => {
    const { result, unmount } = renderHook(() => useDebateReplay(5));
    act(() => result.current.toggle());
    act(() => vi.advanceTimersByTime(1250));
    act(() => result.current.restart());
    expect(result.current.visibleCount).toBe(0);
    expect(result.current.playing).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    act(() => result.current.toggle());
    expect(vi.getTimerCount()).toBe(1);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("reveals the prepared conversation together when reduced motion is requested", () => {
    vi.stubGlobal("matchMedia", () => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }));
    const { result } = renderHook(() => useDebateReplay(5));
    act(() => result.current.toggle());
    act(() => vi.runOnlyPendingTimers());
    expect(result.current.visibleCount).toBe(5);
    expect(result.current.complete).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
  });
});
