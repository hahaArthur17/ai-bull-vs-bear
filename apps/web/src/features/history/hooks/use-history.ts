import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { DebateRecord } from "@/lib/contracts/research";
import { deleteHistory, listHistory } from "../api";

export function useHistory() {
  return useQuery({
    queryKey: ["history"],
    queryFn: ({ signal }) => listHistory(signal),
    staleTime: 30_000,
    retry: false,
  });
}

export function useDeleteHistory() {
  const client = useQueryClient();
  return useMutation({
    mutationKey: ["history", "delete"],
    mutationFn: deleteHistory,
    onMutate: async (id) => {
      await client.cancelQueries({ queryKey: ["history"] });
      const previous = client.getQueryData<DebateRecord[]>(["history"]);
      client.setQueryData(
        ["history"],
        (previous ?? []).filter((record) => record.id !== id),
      );
      return { previous };
    },
    onError: (_error, _id, context) => client.setQueryData(["history"], context?.previous ?? []),
    onSettled: () => client.invalidateQueries({ queryKey: ["history"] }),
  });
}
