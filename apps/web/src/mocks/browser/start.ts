import { bypass, http, HttpResponse, type RequestHandler } from "msw";
import config from "@/app/config/env";

let startup: Promise<void> | undefined;

export function startMocks(): Promise<void> {
  if (config.dataMode !== "demo" && config.feedbackMode !== "demo") return Promise.resolve();
  startup ??= initializeWorker();
  return startup;
}

async function dataHandlers(): Promise<RequestHandler[]> {
  if (config.dataMode !== "demo") return [];
  const [stocks, watchlist, history, debates] = await Promise.all([
    import("../handlers/stocks"),
    import("../handlers/watchlist"),
    import("../handlers/history"),
    import("../handlers/debates"),
  ]);
  return [
    ...stocks.stockHandlers,
    ...watchlist.watchlistHandlers,
    ...history.historyHandlers,
    ...debates.debateHandlers,
  ];
}

async function feedbackHandlers(): Promise<RequestHandler[]> {
  if (config.feedbackMode !== "demo") return [];
  return (await import("../handlers/feedback")).feedbackHandlers;
}

function liveFeedbackBypass(): RequestHandler[] {
  if (config.feedbackMode !== "api" || !config.feedbackApiBaseUrl) return [];
  const target = `${config.feedbackApiBaseUrl.replace(/\/$/, "")}/feedback`;
  return [
    http.all(target, ({ request }) =>
      request.method === "POST" && request.url === target
        ? fetch(bypass(request))
        : HttpResponse.json(
            { message: "This live feedback request does not match the configured endpoint." },
            { status: 501 },
          ),
    ),
  ];
}

async function initializeWorker(): Promise<void> {
  const { setupWorker } = await import("msw/browser");
  const handlers = [
    ...liveFeedbackBypass(),
    ...(await dataHandlers()),
    ...(await feedbackHandlers()),
  ];
  const missing = http.all("/api/*", () =>
    HttpResponse.json(
      {
        message:
          "This API route is not implemented in the public Demo. No request was sent to a backend.",
      },
      { status: 501 },
    ),
  );
  const worker = setupWorker(...handlers, missing);
  await worker.start({
    quiet: true,
    onUnhandledRequest: "bypass",
    serviceWorker: { url: "/mockServiceWorker.js" },
  });
}
