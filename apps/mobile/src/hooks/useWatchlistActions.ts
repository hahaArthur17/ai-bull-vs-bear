import { useRef, type Dispatch, type RefObject, type SetStateAction } from "react";
import { api } from "../api";

/** BB-005: serialize mutations so an older full-list response cannot win. */
export function useWatchlistActions({
  watchlist,
  setWatchlist,
  setError,
  accountEpoch,
}: {
  watchlist: string[];
  setWatchlist: Dispatch<SetStateAction<string[]>>;
  setError: Dispatch<SetStateAction<string>>;
  accountEpoch: RefObject<number>;
}) {
  const latest = useRef(watchlist);
  latest.current = watchlist;
  const queue = useRef({ account: accountEpoch.current, pending: Promise.resolve() });

  return (ticker: string) => {
    const account = accountEpoch.current;
    // A new account need not wait for an abandoned request's timeout.
    if (queue.current.account !== account) queue.current = { account, pending: Promise.resolve() };
    const update = async () => {
      if (accountEpoch.current !== account) return;
      try {
        const next = latest.current.includes(ticker)
          ? await api.removeFromWatchlist(ticker)
          : await api.addToWatchlist(ticker);
        if (accountEpoch.current === account) {
          latest.current = next.tickers;
          setWatchlist(next.tickers);
        }
      } catch (failure) {
        if (accountEpoch.current === account)
          setError(failure instanceof Error ? failure.message : "Could not update the watchlist.");
      }
    };
    queue.current.pending = queue.current.pending.then(update, update);
    return queue.current.pending;
  };
}
