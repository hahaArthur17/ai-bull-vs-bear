#!/usr/bin/env node

/**
 * Local-only request proxy for visual review failure/recovery scenarios.
 *
 * This process is intentionally outside the app bundle. It forwards normal
 * requests to a loopback review-fixture API and injects one safe, repeatable
 * response for the selected route. It never logs request headers or bodies.
 */

import http from "node:http";
import net from "node:net";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const DEFAULT_UPSTREAM = "http://127.0.0.1:8000";
const DEFAULT_LISTEN_HOST = "127.0.0.1";
const DEFAULT_LISTEN_PORT = 8010;
const MAX_REQUEST_BYTES = 2 * 1024 * 1024;

const RECOVERABLE_SCENARIOS = new Map([
  ["watchlist-recover", { method: "GET", match: (url) => url.pathname === "/watchlist" }],
  ["search-recover", { method: "GET", match: (url) => url.pathname === "/stocks" && url.searchParams.has("q") }],
  ["bundle-recover", { method: "GET", match: (url) => /^\/stocks\/[^/]+\/bundle$/.test(url.pathname) }],
  ["examination-recover", { method: "POST", match: (url) => /^\/claims\/[^/]+\/examine$/.test(url.pathname) }],
  ["explanation-recover", { method: "POST", match: (url) => /^\/debates\/[^/]+\/explanations$/.test(url.pathname) }],
]);

function isLoopbackHost(hostname) {
  const normalized = hostname.replace(/^\[|\]$/g, "").toLowerCase();
  if (normalized === "localhost" || normalized === "::1") return true;
  return net.isIP(normalized) === 4 && normalized.startsWith("127.");
}

function assertLoopbackUrl(raw, label) {
  const parsed = new URL(raw);
  if (parsed.protocol !== "http:") {
    throw new Error(`${label} must use http:// for a local review process`);
  }
  if (!isLoopbackHost(parsed.hostname)) {
    throw new Error(`${label} must target a loopback host`);
  }
  if (parsed.username || parsed.password) {
    throw new Error(`${label} must not contain credentials`);
  }
  if (parsed.pathname !== "/" || parsed.search || parsed.hash) {
    throw new Error(`${label} must contain only a local origin`);
  }
  return parsed;
}

function parseListenHost(raw) {
  if (!raw || !isLoopbackHost(raw)) {
    throw new Error("listen host must be localhost, 127.0.0.0/8, or ::1");
  }
  return raw;
}

function corsHeaders(request) {
  const origin = request.headers.origin;
  let allowedOrigin = null;
  if (typeof origin === "string") {
    try {
      const parsed = new URL(origin);
      if ((parsed.protocol === "http:" || parsed.protocol === "https:") && isLoopbackHost(parsed.hostname)) {
        allowedOrigin = origin;
      }
    } catch {
      // An invalid or non-local Origin deliberately receives no CORS grant.
    }
  }
  return {
    ...(allowedOrigin ? {
      "access-control-allow-origin": allowedOrigin,
      "access-control-allow-credentials": "true",
    } : {}),
    "access-control-allow-methods": "GET,POST,DELETE,OPTIONS",
    "access-control-allow-headers": "Content-Type,Authorization,X-User-Id",
    vary: "Origin",
  };
}

function jsonResponse(request, response, statusCode, payload) {
  const body = Buffer.from(JSON.stringify(payload));
  response.writeHead(statusCode, {
    ...corsHeaders(request),
    "content-type": "application/json; charset=utf-8",
    "content-length": body.length,
    "cache-control": "no-store",
  });
  response.end(body);
}

function scenarioResponse(request, response, scenario) {
  if (
    scenario === "history-empty"
    && request.method === "GET"
    && (request.url.pathname === "/analysis" || request.url.pathname === "/debates")
  ) {
    jsonResponse(request, response, 200, []);
    return true;
  }
  const definition = RECOVERABLE_SCENARIOS.get(scenario);
  if (!definition || request.method !== definition.method || !definition.match(request.url)) {
    return false;
  }
  jsonResponse(request, response, 503, {
    detail: "Local review scenario injected a recoverable error. Retry to continue.",
  });
  return true;
}

function verifyReviewFixtureUpstream(upstream) {
  return new Promise((resolveVerify, rejectVerify) => {
    const healthUrl = new URL("/health", upstream);
    const request = http.get(healthUrl, { headers: { accept: "application/json" } }, (response) => {
      const chunks = [];
      let total = 0;
      response.on("data", (chunk) => {
        total += chunk.length;
        if (total > 64 * 1024) {
          request.destroy(new Error("review fixture health response is too large"));
          return;
        }
        chunks.push(chunk);
      });
      response.on("end", () => {
        try {
          const payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
          if (response.statusCode !== 200 || payload.data_mode !== "review_fixture") {
            rejectVerify(new Error("upstream must report data_mode=review_fixture"));
            return;
          }
          resolveVerify();
        } catch {
          rejectVerify(new Error("upstream returned an invalid review fixture health response"));
        }
      });
    });
    request.setTimeout(3000, () => request.destroy(new Error("review fixture health check timed out")));
    request.once("error", rejectVerify);
  });
}

function forwardHeaders(request, bodyLength) {
  const allowed = new Set(["accept", "content-type", "user-agent", "x-user-id"]);
  const headers = {};
  for (const [name, value] of Object.entries(request.headers)) {
    if (allowed.has(name) && typeof value === "string") headers[name] = value;
  }
  if (bodyLength > 0) headers["content-length"] = String(bodyLength);
  return headers;
}

async function readBody(request) {
  const chunks = [];
  let total = 0;
  for await (const chunk of request) {
    total += chunk.length;
    if (total > MAX_REQUEST_BYTES) throw new Error("Request body exceeds local review limit");
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

function forwardRequest(request, parsedUrl, response, upstream, body) {
  return new Promise((resolveForward) => {
    const client = http.request(
      {
        protocol: upstream.protocol,
        hostname: upstream.hostname,
        port: upstream.port || 80,
        method: request.method,
        path: `${parsedUrl.pathname}${parsedUrl.search}`,
        headers: forwardHeaders(request, body.length),
      },
      (upstreamResponse) => {
        const headers = {};
        for (const [name, value] of Object.entries(upstreamResponse.headers)) {
          if (!name.toLowerCase().startsWith("access-control-")) headers[name] = value;
        }
        Object.assign(headers, corsHeaders(request));
        delete headers["content-encoding"];
        response.writeHead(upstreamResponse.statusCode || 502, headers);
        upstreamResponse.pipe(response);
        upstreamResponse.once("end", resolveForward);
      },
    );
    client.once("error", () => {
      if (!response.headersSent) {
        jsonResponse(request, response, 502, {
          detail: "Local review API is unreachable. Start the review-fixture backend and retry.",
        });
      }
      resolveForward();
    });
    if (body.length) client.write(body);
    client.end();
  });
}

export function createReviewScenarioProxy({
  scenario = "passthrough",
  upstreamUrl = DEFAULT_UPSTREAM,
  listenHost = DEFAULT_LISTEN_HOST,
  listenPort = DEFAULT_LISTEN_PORT,
} = {}) {
  const upstream = assertLoopbackUrl(upstreamUrl, "upstream URL");
  const host = parseListenHost(listenHost);
  if (scenario !== "passthrough" && scenario !== "history-empty" && !RECOVERABLE_SCENARIOS.has(scenario)) {
    throw new Error(`unknown review scenario: ${scenario}`);
  }
  const injected = new Set();
  const server = http.createServer(async (request, response) => {
    if (request.method === "OPTIONS") {
      response.writeHead(204, corsHeaders(request));
      response.end();
      return;
    }
    let parsedUrl;
    try {
      parsedUrl = new URL(request.url || "/", `http://${request.headers.host || "localhost"}`);
    } catch {
      jsonResponse(request, response, 400, { detail: "Invalid local review request" });
      return;
    }
    const bodyPromise = readBody(request);
    let body;
    try {
      body = await bodyPromise;
    } catch (error) {
      jsonResponse(request, response, 413, { detail: error instanceof Error ? error.message : "Request body rejected" });
      return;
    }
    const reviewRequest = {
      method: request.method,
      headers: request.headers,
      url: parsedUrl,
    };
    try {
      await verifyReviewFixtureUpstream(upstream);
    } catch {
      jsonResponse(request, response, 502, {
        detail: "Local review proxy stopped because the upstream is not an isolated review fixture.",
      });
      return;
    }
    const key = `${request.method} ${parsedUrl.pathname}`;
    if (scenario === "history-empty" && scenarioResponse(reviewRequest, response, scenario)) {
      return;
    }
    if (RECOVERABLE_SCENARIOS.has(scenario) && !injected.has(key)) {
      const injectedNow = scenarioResponse(reviewRequest, response, scenario);
      if (injectedNow) {
        injected.add(key);
        return;
      }
    }
    await forwardRequest(request, parsedUrl, response, upstream, body);
  });
  return {
    server,
    async listen() {
      await verifyReviewFixtureUpstream(upstream);
      return new Promise((resolveListen, rejectListen) => {
        const onError = (error) => {
          server.off("listening", onListening);
          rejectListen(error);
        };
        const onListening = () => {
          server.off("error", onError);
          resolveListen(server.address());
        };
        server.once("error", onError);
        server.once("listening", onListening);
        server.listen(listenPort, host);
      });
    },
    close() {
      return new Promise((resolveClose) => server.close(() => resolveClose()));
    },
  };
}

function parseArgs(argv) {
  const values = {
    scenario: process.env.REVIEW_SCENARIO || "passthrough",
    upstreamUrl: process.env.REVIEW_UPSTREAM_URL || DEFAULT_UPSTREAM,
    listenHost: process.env.REVIEW_PROXY_HOST || DEFAULT_LISTEN_HOST,
    listenPort: Number(process.env.REVIEW_PROXY_PORT || DEFAULT_LISTEN_PORT),
  };
  for (const argument of argv) {
    const [key, value] = argument.split("=", 2);
    if (key === "--scenario") values.scenario = value;
    if (key === "--upstream") values.upstreamUrl = value;
    if (key === "--host") values.listenHost = value;
    if (key === "--port") values.listenPort = Number(value);
  }
  if (!Number.isInteger(values.listenPort) || values.listenPort < 0 || values.listenPort > 65535) {
    throw new Error("listen port must be an integer from 0 to 65535");
  }
  return values;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  try {
    const options = parseArgs(process.argv.slice(2));
    const proxy = createReviewScenarioProxy(options);
    const address = await proxy.listen();
    const port = typeof address === "object" && address ? address.port : options.listenPort;
    process.stdout.write(`review scenario proxy listening on ${options.listenHost}:${port} (scenario=${options.scenario})\n`);
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : "Could not start review scenario proxy"}\n`);
    process.exitCode = 1;
  }
}
