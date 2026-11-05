// @vitest-environment node
/// <reference types="node" />
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { getResponse, type RequestHandler } from "msw";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

const modes = vi.hoisted(() => ({
  dataMode: "demo" as "demo" | "api",
  feedbackMode: "demo" as "demo" | "api" | "disabled",
  apiBaseUrl: "",
  feedbackApiBaseUrl: "",
}));
const registered = vi.hoisted(() => ({ handlers: [] as RequestHandler[] }));

vi.mock("@/app/config/env", () => ({ config: modes, default: modes }));
// Capture the real handlers without requiring a browser Service Worker in Node.
// Requests below still run through MSW's resolver and, when appropriate, real HTTP.
vi.mock("msw/browser", () => ({
  setupWorker: (...handlers: RequestHandler[]) => {
    registered.handlers = handlers;
    return { start: async () => {} };
  },
}));

type ReceivedRequest = {
  method: string;
  path: string;
  body: string;
  contentType: string;
  key: string;
};
const received: ReceivedRequest[] = [];
let receiver: Server;
let origin: string;

beforeAll(async () => {
  receiver = createServer(async (request, response) => {
    const chunks: Buffer[] = [];
    for await (const chunk of request) chunks.push(Buffer.from(chunk));
    received.push({
      method: request.method ?? "",
      path: request.url ?? "",
      body: Buffer.concat(chunks).toString("utf8"),
      contentType: request.headers["content-type"] ?? "",
      key: String(request.headers["idempotency-key"] ?? ""),
    });
    response.setHeader("Content-Type", "application/json");
    if (request.url === "/api/stocks") {
      response.end(JSON.stringify({ source: "real-receiver", tickers: ["LIVE"] }));
      return;
    }
    response.statusCode = 201;
    response.end(
      JSON.stringify({
        id: "real_feedback_confirmed",
        mode: "api",
        status: "received",
        submittedAt: "2026-11-05T00:00:00Z",
        attachmentCount: 1,
      }),
    );
  });
  await new Promise<void>((resolve, reject) => {
    receiver.once("error", reject);
    receiver.listen(0, "127.0.0.1", resolve);
  });
  origin = `http://127.0.0.1:${(receiver.address() as AddressInfo).port}`;
});

beforeEach(() => {
  vi.resetModules();
  registered.handlers = [];
  received.length = 0;
  modes.apiBaseUrl = `${origin}/api`;
  modes.feedbackApiBaseUrl = `${origin}/api`;
});

afterAll(async () => {
  receiver.closeAllConnections();
  await new Promise<void>((resolve, reject) =>
    receiver.close((error) => (error ? reject(error) : resolve())),
  );
});

async function start(dataMode: "demo" | "api", feedbackMode: "demo" | "api" | "disabled") {
  modes.dataMode = dataMode;
  modes.feedbackMode = feedbackMode;
  await (await import("./start")).startMocks();
}

async function resolveOrReachReceiver(request: Request) {
  const mocked = await getResponse(registered.handlers, request, { baseUrl: origin });
  return mocked ?? fetch(request);
}

function feedbackRequest(key: string) {
  const body = new FormData();
  body.set(
    "feedback",
    JSON.stringify({
      category: "suggestion",
      title: "Clearer chart labels",
      description: "Please make the chart legend easier to read on smaller screens.",
      relatedPage: "research",
      experienceRating: null,
      reproductionSteps: null,
      expectedResult: null,
      actualResult: null,
      fullName: null,
      email: null,
      gender: null,
      wantsReply: false,
    }),
  );
  body.append(
    "attachments",
    new Blob(["synthetic diagnostic context"], { type: "application/pdf" }),
    "context.pdf",
  );
  return new Request(`${origin}/api/feedback`, {
    method: "POST",
    headers: { "Idempotency-Key": key },
    body,
  });
}

describe("research and feedback mode isolation", () => {
  it("lets same-origin live research reach the receiver while feedback stays simulated", async () => {
    await start("api", "demo");
    const research = await resolveOrReachReceiver(new Request(`${origin}/api/stocks`));
    expect(research.status).toBe(200);
    expect(await research.json()).toEqual({ source: "real-receiver", tickers: ["LIVE"] });
    const feedback = await resolveOrReachReceiver(feedbackRequest("demo-only-feedback"));
    expect(await feedback.json()).toMatchObject({ mode: "demo", status: "simulated" });
    expect(received.map(({ method, path }) => ({ method, path }))).toEqual([
      { method: "GET", path: "/api/stocks" },
    ]);
  });

  it("sends real multipart feedback to the receiver even while research is a Demo", async () => {
    await start("demo", "api");
    const research = await resolveOrReachReceiver(new Request(`${origin}/api/stocks?q=apple`));
    expect(await research.json()).toEqual(
      expect.arrayContaining([expect.objectContaining({ ticker: "AAPL" })]),
    );
    const feedback = await resolveOrReachReceiver(feedbackRequest("live-feedback-key"));
    expect(feedback.status).toBe(201);
    expect(await feedback.json()).toMatchObject({
      id: "real_feedback_confirmed",
      mode: "api",
      status: "received",
    });
    expect(received).toHaveLength(1);
    expect(received[0]).toMatchObject({
      method: "POST",
      path: "/api/feedback",
      key: "live-feedback-key",
    });
    expect(received[0].contentType).toContain("multipart/form-data; boundary=");
    expect(received[0].body).toContain('name="feedback"');
    expect(received[0].body).toContain('filename="context.pdf"');
    expect(received[0].body).toContain("synthetic diagnostic context");
  });

  it("keeps unimplemented Demo API requests local instead of reaching a backend", async () => {
    await start("demo", "demo");
    const response = await resolveOrReachReceiver(new Request(`${origin}/api/not-implemented`));
    expect(response.status).toBe(501);
    expect(await response.json()).toMatchObject({
      message: expect.stringContaining("No request was sent"),
    });
    expect(received).toHaveLength(0);
  });

  it("lets an entirely live application reach both receiver endpoints", async () => {
    await start("api", "api");
    const research = await resolveOrReachReceiver(new Request(`${origin}/api/stocks`));
    const feedback = await resolveOrReachReceiver(feedbackRequest("all-live-key"));
    expect(await research.json()).toMatchObject({ source: "real-receiver" });
    expect(await feedback.json()).toMatchObject({ mode: "api", status: "received" });
    expect(received.map((request) => request.path)).toEqual(["/api/stocks", "/api/feedback"]);
  });
});
