import { act, renderHook } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { useAnalysisHistory } from "../hooks/useAnalysisHistory";
import type { AnalysisHistoryPage, AnalysisResponse } from "../types";

const row = (id: string) => ({ analysis_id: id }) as AnalysisResponse;

test("history pages are bounded and overlapping IDs are merged once", async () => {
  const page = vi.fn().mockResolvedValue({ items: [row("49"), row("50")], next_offset: null });
  const { result } = renderHook(() => useAnalysisHistory(page));
  act(() =>
    result.current.replace({
      items: Array.from({ length: 50 }, (_, i) => row(String(i))),
      next_offset: 50,
    }),
  );
  await act(() => result.current.loadMore());
  expect(page).toHaveBeenCalledWith(50, 50);
  expect(result.current.history).toHaveLength(51);
  expect(result.current.hasMore).toBe(false);
});

test("an abandoned history page cannot populate a different account", async () => {
  let finish!: (value: AnalysisHistoryPage) => void;
  const page = vi.fn().mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { result } = renderHook(() => useAnalysisHistory(page));
  act(() =>
    result.current.replace({
      items: Array.from({ length: 50 }, (_, i) => row(String(i))),
      next_offset: 50,
    }),
  );
  act(() => {
    void result.current.loadMore();
  });
  act(() => result.current.reset());
  act(() => result.current.replace({ items: [row("new-account")], next_offset: null }));
  await act(async () => finish({ items: [row("old-account")], next_offset: null }));
  expect(result.current.history.map((item) => item.analysis_id)).toEqual(["new-account"]);
});

test("an empty parsed legacy page retains the server's continuation cursor", async () => {
  const page = vi.fn().mockResolvedValue({ items: [row("older-valid-result")], next_offset: null });
  const { result } = renderHook(() => useAnalysisHistory(page));
  act(() => result.current.replace({ items: [], next_offset: 50 }));
  expect(result.current.hasMore).toBe(true);
  await act(() => result.current.loadMore());
  expect(result.current.history[0].analysis_id).toBe("older-valid-result");
});
