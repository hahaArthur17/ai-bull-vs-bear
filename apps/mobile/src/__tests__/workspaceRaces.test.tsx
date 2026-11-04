import { act, renderHook } from "@testing-library/react";
import { useRef, useState } from "react";
import { expect, test, vi } from "vitest";
import { api } from "../api";
import { useClaimExamination } from "../hooks/useClaimExamination";
import { useWatchlistActions } from "../hooks/useWatchlistActions";
import type { Claim, ExaminationResponse, WatchlistResponse } from "../types";

vi.mock("../api", () => ({
  api: {
    addToWatchlist: vi.fn(),
    removeFromWatchlist: vi.fn(),
  },
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => {
    resolve = yes;
    reject = no;
  });
  return { promise, resolve, reject };
}
const claim = (id: string): Claim => ({
  id,
  agent: "bull",
  text: id,
  evidence_ids: [],
  signal_strength: "weak",
  confidence: "low",
  risk_meaning: "Uncertain",
  terms: [],
});
const answer = (id: string): ExaminationResponse => ({
  claim_id: id,
  question_type: "evidence_support",
  answer: id,
  evidence: [],
  disclaimer: "Educational",
});

test.each([false, true])(
  "BB-004: an old claim response cannot overwrite the new dialog (failure=%s)",
  async (fails) => {
    const old = deferred<ExaminationResponse>();
    const examine = vi.fn().mockReturnValueOnce(old.promise).mockResolvedValueOnce(answer("B"));
    const { result } = renderHook(() => useClaimExamination(examine));
    act(() => result.current.open(claim("A")));
    act(() => {
      void result.current.ask("evidence_support");
      void result.current.ask("risk_meaning");
    });
    expect(examine).toHaveBeenCalledTimes(1);
    act(() => result.current.open(claim("B")));
    await act(() => result.current.ask("evidence_support"));
    await act(async () => {
      if (fails) old.reject(new Error("Old failure"));
      else old.resolve(answer("A"));
    });
    expect(result.current.result?.claim_id).toBe("B");
    expect(result.current.error).toBe("");
    expect(result.current.pendingQuestion).toBeNull();
  },
);

function useWatchlistHarness() {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [error, setError] = useState("");
  const accountEpoch = useRef(0);
  const toggle = useWatchlistActions({ watchlist, setWatchlist, setError, accountEpoch });
  return {
    watchlist,
    error,
    toggle,
    reset: () => {
      accountEpoch.current++;
      setWatchlist([]);
    },
  };
}

test("BB-005: successive mutations use the settled list, including a repeated ticker", async () => {
  vi.mocked(api.addToWatchlist).mockReset();
  vi.mocked(api.removeFromWatchlist).mockReset();
  const first = deferred<WatchlistResponse>();
  vi.mocked(api.addToWatchlist)
    .mockReturnValueOnce(first.promise)
    .mockResolvedValueOnce({ user_id: "u", tickers: ["AAPL", "GOOG"] });
  vi.mocked(api.removeFromWatchlist).mockResolvedValue({ user_id: "u", tickers: ["GOOG"] });
  const { result } = renderHook(useWatchlistHarness);
  let updates: Promise<void>[] = [];
  await act(async () => {
    updates = [
      result.current.toggle("AAPL"),
      result.current.toggle("GOOG"),
      result.current.toggle("AAPL"),
    ];
  });
  expect(api.addToWatchlist).toHaveBeenCalledTimes(1);
  await act(async () => {
    first.resolve({ user_id: "u", tickers: ["AAPL"] });
    await Promise.all(updates);
  });
  expect(api.addToWatchlist).toHaveBeenCalledTimes(2);
  expect(api.removeFromWatchlist).toHaveBeenCalledWith("AAPL");
  expect(result.current.watchlist).toEqual(["GOOG"]);
});

test("BB-005: switching accounts discards queued writes and late responses", async () => {
  vi.mocked(api.addToWatchlist).mockReset();
  const old = deferred<WatchlistResponse>();
  vi.mocked(api.addToWatchlist)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce({ user_id: "b", tickers: ["GOOG"] });
  const { result } = renderHook(useWatchlistHarness);
  let queued: Promise<void>[] = [];
  await act(async () => {
    queued = [result.current.toggle("AAPL"), result.current.toggle("MSFT")];
  });
  act(() => result.current.reset());
  await act(() => result.current.toggle("GOOG"));
  await act(async () => {
    old.resolve({ user_id: "a", tickers: ["AAPL"] });
    await Promise.all(queued);
  });
  expect(result.current.watchlist).toEqual(["GOOG"]);
  expect(api.addToWatchlist).toHaveBeenCalledTimes(2);
});
