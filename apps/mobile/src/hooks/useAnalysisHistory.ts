import { useCallback, useRef, useState } from "react";
import type { AnalysisHistoryPage, AnalysisResponse } from "../types";

const PAGE_SIZE = 50;

/** Keep history requests bounded and invalidate old pages after an account reset. */
export function useAnalysisHistory(
  listPage: (limit: number, offset: number) => Promise<AnalysisHistoryPage>,
) {
  const [history, setHistory] = useState<AnalysisResponse[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const hasMore = nextOffset !== null;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const context = useRef(0);
  const active = useRef<symbol | null>(null);

  const replace = useCallback((page: AnalysisHistoryPage) => {
    context.current++;
    active.current = null;
    setHistory(page.items);
    setNextOffset(page.next_offset);
    setLoading(false);
    setError("");
  }, []);
  const reset = useCallback(() => replace({ items: [], next_offset: null }), [replace]);

  const loadMore = async () => {
    if (nextOffset === null || active.current) return;
    const request = Symbol("history-page");
    const pageContext = context.current;
    active.current = request;
    setLoading(true);
    setError("");
    try {
      const page = await listPage(PAGE_SIZE, nextOffset);
      if (context.current !== pageContext) return;
      // A newly saved analysis can shift an offset-based page. Merge by ID so
      // that overlapping pages never produce duplicate history cards.
      setHistory((current) => [
        ...new Map([...current, ...page.items].map((row) => [row.analysis_id, row])).values(),
      ]);
      setNextOffset(page.next_offset);
    } catch (failure) {
      if (context.current === pageContext)
        setError(failure instanceof Error ? failure.message : "Could not load older analyses.");
    } finally {
      if (active.current === request) {
        active.current = null;
        setLoading(false);
      }
    }
  };

  return { history, setHistory, replace, reset, hasMore, loading, error, loadMore };
}
