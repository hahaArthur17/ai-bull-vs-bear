import { delay, http, HttpResponse } from "msw";
import { findStock, makeResearch, stocks } from "@/mocks/fixtures/market";
import { getDemoScenario } from "@/mocks/state/scenarios";

export const stockHandlers = [
  http.get("/api/stocks", async ({ request }) => {
    const scenario = getDemoScenario();
    await delay(scenario === "slow" ? 2200 : 260);
    if (scenario === "error")
      return HttpResponse.json(
        {
          message:
            "Demo search failed on purpose. Switch to Normal or retry after changing the scenario.",
        },
        { status: 503 },
      );
    if (scenario === "empty") return HttpResponse.json([]);
    const query = new URL(request.url).searchParams.get("q")?.trim().toLowerCase() ?? "";
    return HttpResponse.json(
      stocks.filter((stock) =>
        `${stock.ticker} ${stock.name} ${stock.sector}`.toLowerCase().includes(query),
      ),
    );
  }),
  http.get("/api/stocks/:ticker/bundle", async ({ params }) => {
    await delay(320);
    const research = makeResearch(String(params.ticker));
    return research
      ? HttpResponse.json(research)
      : HttpResponse.json(
          { message: "This security is not part of the demo dataset." },
          { status: 404 },
        );
  }),
  http.get("/api/stocks/:ticker", ({ params }) => {
    const stock = findStock(String(params.ticker));
    return stock
      ? HttpResponse.json(stock)
      : HttpResponse.json({ message: "Demo stock not found." }, { status: 404 });
  }),
];
