import { useEffect, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import config from "@/app/config/env";
import { saveHistory } from "@/features/history/api/history.service";
import type { DebateRecord } from "@/lib/contracts/research";

export function useSaveReplay(record: DebateRecord, complete: boolean) {
  const attempted = useRef(false);
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: saveHistory,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["history"] }),
  });
  const { mutate } = save;

  useEffect(() => {
    if (!complete || attempted.current || config.dataMode !== "demo") return;
    attempted.current = true;
    mutate(record);
  }, [complete, record, mutate]);

  return { ...save, retry: () => mutate(record) };
}
