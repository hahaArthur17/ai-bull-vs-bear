import { delay, http, HttpResponse } from "msw";
import { createDebate } from "@/mocks/fixtures/debates";
import { findStock } from "@/mocks/fixtures/market";
import { readHistory } from "../history";

export const debateHandlers = [
  http.get("/api/demo/debates/:sessionId", async ({ request, params }) => {
    await delay(260);
    const id = String(params.sessionId);
    if (!id.startsWith("demo-")) {
      const saved = readHistory().find((record) => record.id === id);
      return saved
        ? HttpResponse.json(saved)
        : HttpResponse.json(
            {
              message:
                "This saved demo replay could not be found. It may have been removed or reset.",
            },
            { status: 404 },
          );
    }
    const ticker = (new URL(request.url).searchParams.get("ticker") ?? id.slice(5)).toUpperCase();
    if (!findStock(ticker))
      return HttpResponse.json(
        { message: "Select a demo stock before opening a replay." },
        { status: 404 },
      );
    return HttpResponse.json(createDebate(ticker));
  }),
];
