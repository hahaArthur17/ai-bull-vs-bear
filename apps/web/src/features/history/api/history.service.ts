import type { DebateRecord } from "@/lib/contracts/research";
import { debateRecordSchema, historySchema } from "@/lib/contracts/schemas";
import { request, requireDemo } from "@/lib/http";

export async function listHistory(signal?: AbortSignal): Promise<DebateRecord[]> {
  requireDemo("Saved replay history; live authentication");
  return historySchema.parse(await request<unknown>("/history", { signal }));
}

export async function saveHistory(record: DebateRecord): Promise<DebateRecord> {
  requireDemo("Saving a scripted replay");
  return debateRecordSchema.parse(
    await request<unknown>("/history", { method: "POST", body: JSON.stringify(record) }),
  );
}

export async function deleteHistory(id: string): Promise<void> {
  requireDemo("Deleting saved replay history");
  await request<void>(`/history/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function getDebateForReplay(
  sessionId: string,
  ticker?: string,
  signal?: AbortSignal,
): Promise<DebateRecord> {
  requireDemo("Scripted debate replay");
  const query = ticker ? `?ticker=${encodeURIComponent(ticker)}` : "";
  const payload = await request<unknown>(`/demo/debates/${encodeURIComponent(sessionId)}${query}`, {
    signal,
  });
  return debateRecordSchema.parse(payload);
}
