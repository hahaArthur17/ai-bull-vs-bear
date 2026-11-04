import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { readWatchlist, watchlistHandlers } from "@/mocks/handlers/watchlist";
import { resetDemoState } from "@/mocks/state/scenarios";
import { useToggleWatchlist, useWatchlist } from "./use-watchlist";

const server = setupServer(...watchlistHandlers);
const clients: QueryClient[] = [];
const releases: (() => void)[] = [];
const initialWatchlist = ["AAPL", "NVDA", "MSFT"];

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  releases.splice(0).forEach((release) => release());
  clients.splice(0).forEach((client) => client.clear());
  server.resetHandlers();
  resetDemoState();
});
afterAll(() => server.close());

function deferredResponse() {
  let release = () => {};
  const promise = new Promise<void>((resolve) => {
    release = resolve;
  });
  releases.push(release);
  return { promise, release };
}

function renderWatchlist() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  clients.push(client);
  function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  const rendered = renderHook(() => ({ watchlist: useWatchlist(), toggle: useToggleWatchlist() }), {
    wrapper: Wrapper,
  });
  return { ...rendered, client };
}

describe("watchlist optimistic mutations", () => {
  it.each([
    { ticker: "META", removing: false },
    { ticker: "AAPL", removing: true },
  ])(
    "updates $ticker before the server confirms and retains the result after a fresh query client",
    async ({ ticker, removing }) => {
      const gate = deferredResponse();
      server.use(
        removing
          ? http.delete("/api/watchlist/:ticker", async () => {
              await gate.promise;
            })
          : http.post("/api/watchlist", async () => {
              await gate.promise;
            }),
      );
      const view = renderWatchlist();
      await waitFor(() => expect(view.result.current.watchlist.data).toEqual(initialWatchlist));

      act(() => view.result.current.toggle.mutate(ticker));
      await waitFor(() =>
        expect(view.result.current.watchlist.data?.includes(ticker)).toBe(!removing),
      );
      expect(view.result.current.toggle.isPending).toBe(true);
      expect(readWatchlist()).toEqual(initialWatchlist);

      act(() => gate.release());
      await waitFor(() => expect(view.result.current.toggle.isSuccess).toBe(true));
      const expected = removing ? ["NVDA", "MSFT"] : [...initialWatchlist, "META"];
      expect(view.result.current.watchlist.data).toEqual(expected);
      view.unmount();

      const refreshed = renderWatchlist();
      await waitFor(() => expect(refreshed.result.current.watchlist.data).toEqual(expected));
    },
  );

  it("rolls back the optimistic result when the write returns 500", async () => {
    const gate = deferredResponse();
    server.use(
      http.post("/api/watchlist", async () => {
        await gate.promise;
        return HttpResponse.json({ message: "Simulated write failed." }, { status: 500 });
      }),
    );
    const view = renderWatchlist();
    await waitFor(() => expect(view.result.current.watchlist.data).toEqual(initialWatchlist));

    act(() => view.result.current.toggle.mutate("META"));
    await waitFor(() => expect(view.result.current.watchlist.data).toContain("META"));
    expect(view.result.current.toggle.isPending).toBe(true);

    act(() => gate.release());
    await waitFor(() => expect(view.result.current.toggle.isError).toBe(true));
    expect(view.result.current.toggle.error?.message).toBe("Simulated write failed.");
    expect(view.result.current.watchlist.data).toEqual(initialWatchlist);
    expect(readWatchlist()).toEqual(initialWatchlist);
  });
});
