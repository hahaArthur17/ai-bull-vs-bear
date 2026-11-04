import { useQuery } from "@tanstack/react-query";
import { getDebateForReplay } from "@/features/history/api/history.service";

export function useDebateRecord(sessionId: string, ticker?: string) {
  return useQuery({
    queryKey: ["debate-replay", sessionId, ticker],
    queryFn: ({ signal }) => getDebateForReplay(sessionId, ticker, signal),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  });
}
