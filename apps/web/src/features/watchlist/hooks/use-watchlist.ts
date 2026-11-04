import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addWatchlist, getWatchlist, removeWatchlist } from "../api";

export function useWatchlist() {
  return useQuery({
    queryKey: ["watchlist"],
    queryFn: ({ signal }) => getWatchlist(signal),
    staleTime: 30_000,
    retry: false,
  });
}

export function useToggleWatchlist() {
  const client = useQueryClient();
  return useMutation({
    mutationKey: ["watchlist", "toggle"],
    scope: { id: "watchlist-write" },
    mutationFn: async (ticker: string) => {
      const current = await getWatchlist();
      return current.includes(ticker) ? removeWatchlist(ticker) : addWatchlist(ticker);
    },
    onMutate: async (ticker) => {
      await client.cancelQueries({ queryKey: ["watchlist"] });
      const previous = client.getQueryData<string[]>(["watchlist"]);
      const current = previous ?? [];
      client.setQueryData(
        ["watchlist"],
        current.includes(ticker) ? current.filter((item) => item !== ticker) : [...current, ticker],
      );
      return { previous };
    },
    onError: (_error, _ticker, context) =>
      client.setQueryData(["watchlist"], context?.previous ?? []),
    onSuccess: (tickers) => client.setQueryData(["watchlist"], tickers),
    onSettled: () => client.invalidateQueries({ queryKey: ["watchlist"] }),
  });
}
