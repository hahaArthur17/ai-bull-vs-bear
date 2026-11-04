import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getResearch, searchStocks } from "../api";

export function useStocks(query: string) {
  const normalized = query.trim();
  const [debounced, setDebounced] = useState(normalized);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(normalized), 250);
    return () => window.clearTimeout(timer);
  }, [normalized]);
  const result = useQuery({
    queryKey: ["stocks", debounced],
    queryFn: ({ signal }) => searchStocks(debounced, signal),
    staleTime: 60_000,
    retry: false,
  });
  return { ...result, isDebouncing: normalized !== debounced };
}

export function useResearch(ticker: string) {
  return useQuery({
    queryKey: ["research", ticker],
    queryFn: ({ signal }) => getResearch(ticker, signal),
    enabled: Boolean(ticker),
    staleTime: 60_000,
    retry: false,
  });
}
