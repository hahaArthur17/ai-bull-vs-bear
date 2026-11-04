import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, test, vi } from "vitest";
import App from "../../App";
import { api } from "../api";
import type { DebateSessionDetail, DebateSessionSummary } from "../types";

const withReviewApi = Boolean(process.env.EXPO_PUBLIC_API_URL);
afterEach(() => vi.restoreAllMocks());

beforeAll(async () => {
  if (withReviewApi) await api.runAnalysis("AAPL");
});

test.skipIf(!withReviewApi)(
  "BB-009: changing securities cannot reuse a saved analysis's evidence or back destination",
  async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("tab", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open classic AAPL analysis" }));
    expect(await screen.findByRole("heading", { name: "Classic Debate" })).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Watchlist" }));
    fireEvent.click(await screen.findByRole("button", { name: /GOOG, Alphabet Inc\./ }));
    fireEvent.click(await screen.findByRole("button", { name: "Evidence board" }));
    expect(await screen.findByLabelText(/^Evidence review-goog-news-001:/)).toBeTruthy();
    expect(screen.queryByLabelText(/^Evidence review-aapl-/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Go back" }));
    expect(await screen.findByRole("button", { name: "Evidence board" })).toBeTruthy();
  },
);

test.skipIf(!withReviewApi)(
  "BB-009: an abandoned history failure cannot appear over a newer saved analysis",
  async () => {
    const summary = pendingHistory();
    let rejectOld!: (error: Error) => void;
    vi.spyOn(api, "getDebate").mockReturnValue(
      new Promise((_resolve, reject) => {
        rejectOld = reject;
      }),
    );
    render(<App />);
    fireEvent.click(await screen.findByRole("tab", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open AAPL Debate: INTERIM JUDGE" }));
    fireEvent.click(screen.getByRole("button", { name: "Open classic AAPL analysis" }));
    expect(await screen.findByRole("heading", { name: "Classic Debate" })).toBeTruthy();
    await act(async () => {
      rejectOld(new Error(`Old failure ${summary.id}`));
    });
    expect(screen.queryByRole("button", { name: /Dismiss error: Old failure/ })).toBeNull();
    expect(screen.getByRole("heading", { name: "Classic Debate" })).toBeTruthy();
  },
);

test.skipIf(!withReviewApi)(
  "BB-009: returning to History does not revive a request from an earlier visit",
  async () => {
    const summary = pendingHistory();
    let resolveOld!: (detail: DebateSessionDetail) => void;
    vi.spyOn(api, "getDebate").mockReturnValue(
      new Promise((resolve) => {
        resolveOld = resolve;
      }),
    );
    render(<App />);
    fireEvent.click(await screen.findByRole("tab", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open AAPL Debate: INTERIM JUDGE" }));
    fireEvent.click(screen.getByRole("tab", { name: "Watchlist" }));
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    await act(async () => {
      resolveOld({ session: summary, messages: [], execution_mode: "synchronous_preview" });
    });
    expect(screen.getByRole("heading", { name: /^History$/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Go back" })).toBeNull();
  },
);

function pendingHistory(): DebateSessionSummary {
  const summary: DebateSessionSummary = {
    id: "pending-history-session",
    ticker: "AAPL",
    status: "awaiting_user",
    active_branch_id: "branch",
    active_generation_id: "generation",
    opening_side: "bull",
    created_at: "2026-10-17T00:00:00Z",
    updated_at: "2026-10-17T00:00:00Z",
  };
  vi.spyOn(api, "listDebates").mockResolvedValue([summary]);
  return summary;
}

test.skipIf(!withReviewApi)(
  "BB-009: reopening a saved analysis loads its own stock before returning to research",
  async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: /GOOG, Alphabet Inc\./ }));
    expect(await screen.findByRole("button", { name: "Evidence board" })).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    fireEvent.click(await screen.findByRole("button", { name: "Open classic AAPL analysis" }));
    expect(await screen.findByRole("heading", { name: "Classic Debate" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Go back" }));
    expect(await screen.findByRole("button", { name: "Evidence board" })).toBeTruthy();
    expect(await screen.findByText("Apple Inc.")).toBeTruthy();
    expect(screen.queryByText("Alphabet Inc.")).toBeNull();
  },
);
