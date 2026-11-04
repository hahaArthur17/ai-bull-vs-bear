import { delay, http, HttpResponse } from "msw";
import type { DebateRecord } from "@/lib/contracts/research";
import { debateRecordSchema, historySchema } from "@/lib/contracts/schemas";
import { readDemoValue, writeDemoValue } from "@/lib/storage";
import { createDebate, seedHistory } from "@/mocks/fixtures/debates";
import { findStock } from "@/mocks/fixtures/market";

export function readHistory(): DebateRecord[] {
  return readDemoValue("history", historySchema, seedHistory());
}

export const historyHandlers = [
  http.get("/api/history", async () => {
    await delay(220);
    return HttpResponse.json(readHistory());
  }),
  http.post("/api/history", async ({ request }) => {
    const result = debateRecordSchema.safeParse(await request.json());
    if (!result.success || !findStock(result.data.ticker))
      return HttpResponse.json(
        { message: "Only a valid synthetic demo replay can be saved." },
        { status: 422 },
      );
    await delay(180);
    const incoming = result.data;
    const record = {
      ...createDebate(incoming.ticker),
      id: incoming.id,
      createdAt: incoming.createdAt,
    };
    const history = [record, ...readHistory().filter((item) => item.id !== record.id)].slice(0, 30);
    writeDemoValue("history", history);
    return HttpResponse.json(record, { status: 201 });
  }),
  http.delete("/api/history/:id", async ({ params }) => {
    await delay(160);
    writeDemoValue(
      "history",
      readHistory().filter((item) => item.id !== params.id),
    );
    return new HttpResponse(null, { status: 204 });
  }),
];
