#!/usr/bin/env node

/**
 * Local-only request proxy for visual review failure/recovery scenarios.
 *
 * This process is intentionally outside the app bundle. It forwards normal
 * requests to a loopback review-fixture API and injects one safe, repeatable
 * response for the selected route. It never logs request headers or bodies.
 */

import http from "node:http";
import { createHash } from "node:crypto";
import net from "node:net";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const DEFAULT_UPSTREAM = "http://127.0.0.1:8000";
const DEFAULT_LISTEN_HOST = "127.0.0.1";
const DEFAULT_LISTEN_PORT = 8010;
const MAX_REQUEST_BYTES = 2 * 1024 * 1024;
const V2_REVIEW_EPOCH_MS = Date.parse("2026-01-01T00:00:00.000Z");

const RECOVERABLE_SCENARIOS = new Map([
  ["watchlist-recover", { method: "GET", match: (url) => url.pathname === "/watchlist" }],
  ["search-recover", { method: "GET", match: (url) => url.pathname === "/stocks" && url.searchParams.has("q") }],
  ["bundle-recover", { method: "GET", match: (url) => /^\/stocks\/[^/]+\/bundle$/.test(url.pathname) }],
  ["examination-recover", { method: "POST", match: (url) => /^\/claims\/[^/]+\/examine$/.test(url.pathname) }],
  ["explanation-recover", { method: "POST", match: (url) => /^\/debates\/[^/]+\/explanations$/.test(url.pathname) }],
]);

const V2_TRANSIENT_SCENARIOS = new Set([
  "v2-reconnect",
  "v2-retry",
  "v2-cancel",
  "v2-failure",
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

function requestUpstreamJson(request, parsedUrl, upstream, body) {
  return new Promise((resolveRequest, rejectRequest) => {
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
        const chunks = [];
        let total = 0;
        upstreamResponse.on("data", (chunk) => {
          total += chunk.length;
          if (total > MAX_REQUEST_BYTES) {
            client.destroy(new Error("Review fixture response exceeds local review limit"));
            return;
          }
          chunks.push(chunk);
        });
        upstreamResponse.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          let payload = null;
          try {
            payload = text ? JSON.parse(text) : null;
          } catch {
            rejectRequest(new Error("Review fixture returned an invalid JSON Debate response"));
            return;
          }
          resolveRequest({ statusCode: upstreamResponse.statusCode || 502, payload });
        });
      },
    );
    client.setTimeout(3000, () => {
      client.destroy(new Error("review fixture Debate request timed out"));
    });
    client.once("error", rejectRequest);
    if (body.length) client.write(body);
    client.end();
  });
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function reviewTimestamp(baseTimeMs, step) {
  return new Date(baseTimeMs + step * 1000).toISOString();
}

function reviewEpoch(detail) {
  const source = detail.session.updated_at || detail.session.created_at;
  const parsed = typeof source === "string" ? Date.parse(source) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : V2_REVIEW_EPOCH_MS;
}

function deterministicUuid(seed) {
  const bytes = createHash("sha256").update(seed).digest().subarray(0, 16);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = bytes.toString("hex");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function isDebateDetail(value) {
  return isRecord(value)
    && isRecord(value.session)
    && typeof value.session.id === "string"
    && typeof value.session.active_generation_id === "string"
    && Array.isArray(value.messages);
}

function scenarioJob(detail) {
  if (isRecord(detail.job) && typeof detail.job.id === "string") return detail.job;
  if (typeof detail.job_id !== "string") {
    throw new Error("Review fixture Debate response did not include a valid job identifier");
  }
  return {
    id: detail.job_id,
    session_id: detail.session.id,
    job_type: "round_1",
    status: "queued",
    attempt_count: 0,
    max_attempts: 3,
    safe_error_code: null,
  };
}

function setRunningDetail(detail, attemptCount, timestamp) {
  const next = cloneJson(detail);
  next.session.status = "running_round_1";
  next.session.completed_at = null;
  next.session.interim_judge_message_id = null;
  next.session.final_judge_message_id = null;
  next.session.safe_error_code = null;
  next.session.updated_at = timestamp;
  next.messages = [];
  const job = scenarioJob(next);
  job.status = "running";
  job.attempt_count = attemptCount;
  job.safe_error_code = null;
  job.started_at = timestamp;
  job.finished_at = null;
  job.updated_at = timestamp;
  next.job = job;
  return next;
}

function setQueuedRetryDetail(detail, attemptCount, timestamp) {
  const next = cloneJson(detail);
  next.session.status = "queued_round_1";
  next.session.completed_at = null;
  next.session.interim_judge_message_id = null;
  next.session.final_judge_message_id = null;
  next.session.safe_error_code = null;
  next.session.updated_at = timestamp;
  const job = scenarioJob(next);
  job.status = "queued";
  job.attempt_count = attemptCount;
  job.safe_error_code = null;
  job.finished_at = null;
  job.updated_at = timestamp;
  next.job = job;
  return next;
}

function setTerminalDetail(detail, status, safeErrorCode, timestamp) {
  const next = cloneJson(detail);
  next.session.status = status;
  next.session.completed_at = timestamp;
  next.session.safe_error_code = safeErrorCode;
  next.session.updated_at = timestamp;
  const job = scenarioJob(next);
  job.status = status === "failed" ? "failed" : "cancelled";
  job.safe_error_code = safeErrorCode;
  job.finished_at = timestamp;
  job.started_at ||= timestamp;
  job.updated_at = timestamp;
  next.job = job;
  return next;
}

function createV2State(original, scenario) {
  if (!isDebateDetail(original)) {
    throw new Error("Review fixture Debate response did not contain a valid Session detail");
  }
  const baseTimeMs = reviewEpoch(original);
  let detail = setRunningDetail(original, 1, reviewTimestamp(baseTimeMs, 0));
  if (scenario === "v2-retry") {
    detail = setQueuedRetryDetail(detail, 1, reviewTimestamp(baseTimeMs, 0));
  }
  const job = scenarioJob(detail);
  return {
    scenario,
    detail,
    sessionId: detail.session.id,
    generationId: detail.session.active_generation_id,
    jobId: job.id,
    baseTimeMs,
    events: [],
    nextSequence: 1,
    sseRequests: 0,
    subscribers: new Set(),
  };
}

function appendV2Event(state, type, payload) {
  const event = {
    version: 1,
    event_id: deterministicUuid(`${state.sessionId}:event:${state.nextSequence}`),
    session_id: state.sessionId,
    sequence: state.nextSequence,
    type,
    timestamp: reviewTimestamp(state.baseTimeMs, state.nextSequence),
    payload,
  };
  state.nextSequence += 1;
  state.events.push(event);
  for (const subscriber of state.subscribers) writeSseEvent(subscriber.response, event);
  return event;
}

function writeSseEvent(response, event) {
  response.write(`id: ${event.sequence}\nevent: ${event.type}\ndata: ${JSON.stringify(event)}\n\n`);
}

function parseAfterSequence(url) {
  const raw = url.searchParams.get("after_sequence");
  if (raw === null || raw === "") return 0;
  const value = Number(raw);
  return Number.isInteger(value) && value >= 0 ? value : 0;
}

function sendSseHeaders(request, response) {
  response.writeHead(200, {
    ...corsHeaders(request),
    "content-type": "text/event-stream; charset=utf-8",
    "cache-control": "no-cache, no-transform",
    connection: "keep-alive",
    "x-accel-buffering": "no",
  });
}

function attachV2Subscriber(request, response, state, afterSequence, closeAfterWrite = false) {
  sendSseHeaders(request, response);
  for (const event of state.events) {
    if (event.sequence > afterSequence) writeSseEvent(response, event);
  }
  if (closeAfterWrite) {
    response.end();
    return;
  }
  const subscriber = { response };
  state.subscribers.add(subscriber);
  request.once("close", () => state.subscribers.delete(subscriber));
  response.once("close", () => state.subscribers.delete(subscriber));
}

function v2StartEvent(state, attemptCount) {
  appendV2Event(state, "job.started", {
    job_id: state.jobId,
    job_type: state.detail.job.job_type,
    attempt_count: attemptCount,
  });
}

function serveV2Events(request, response, state, url) {
  const afterSequence = parseAfterSequence(url);
  state.sseRequests += 1;
  if (state.scenario === "v2-reconnect") {
    if (state.sseRequests === 1) {
      v2StartEvent(state, 1);
      attachV2Subscriber(request, response, state, afterSequence, true);
      return;
    }
    if (state.sseRequests === 2) {
      state.detail = setRunningDetail(state.detail, 2, reviewTimestamp(state.baseTimeMs, 2));
      v2StartEvent(state, 2);
    }
    attachV2Subscriber(request, response, state, afterSequence);
    return;
  }
  if (state.scenario === "v2-retry") {
    if (state.events.length === 0) {
      appendV2Event(state, "job.retry_scheduled", {
        generation_id: state.generationId,
        job_id: state.jobId,
        job_type: state.detail.job.job_type,
        attempt_count: 1,
        retry_delay_seconds: 4,
      });
    }
    attachV2Subscriber(request, response, state, afterSequence);
    return;
  }
  if (state.scenario === "v2-failure") {
    if (state.events.length === 0) {
      v2StartEvent(state, 1);
      state.detail = setTerminalDetail(
        state.detail,
        "failed",
        "review_fixture_failure",
        reviewTimestamp(state.baseTimeMs, 3),
      );
      appendV2Event(state, "job.failed", {
        generation_id: state.generationId,
        job_id: state.jobId,
        job_type: state.detail.job.job_type,
        attempt_count: 1,
        safe_error_code: "review_fixture_failure",
        status: "failed",
      });
      appendV2Event(state, "session.failed", {
        generation_id: state.generationId,
        job_id: state.jobId,
        safe_error_code: "review_fixture_failure",
        status: "failed",
      });
    }
    attachV2Subscriber(request, response, state, afterSequence, true);
    return;
  }
  if (state.scenario === "v2-cancel") {
    if (state.events.length === 0) v2StartEvent(state, 1);
    attachV2Subscriber(request, response, state, afterSequence);
  }
}

function cancelV2Scenario(state) {
  if (state.detail.session.status === "cancelled") return state.detail;
  const cancelledGenerationId = state.generationId;
  const nextGenerationId = deterministicUuid(`${state.sessionId}:cancel:${cancelledGenerationId}`);
  state.generationId = nextGenerationId;
  appendV2Event(state, "session.cancel_requested", {
    generation_id: nextGenerationId,
    cancelled_generation_id: cancelledGenerationId,
    status: "cancel_requested",
  });
  state.detail = setTerminalDetail(
    state.detail,
    "cancelled",
    null,
    reviewTimestamp(state.baseTimeMs, 4),
  );
  state.detail.session.active_generation_id = nextGenerationId;
  appendV2Event(state, "session.cancelled", {
    generation_id: nextGenerationId,
    status: "cancelled",
  });
  // This valid late draft belongs to the invalidated generation and must never
  // become canonical. The client reducer should retain only the cancelled detail.
  const lateMessageId = deterministicUuid(`${state.sessionId}:late-draft:${cancelledGenerationId}`);
  appendV2Event(state, "turn.started", {
    generation_id: cancelledGenerationId,
    message_id: lateMessageId,
    role: "bull",
  });
  appendV2Event(state, "turn.delta", {
    generation_id: cancelledGenerationId,
    message_id: lateMessageId,
    delta_index: 1,
    delta: "Late simulated output that must not persist.",
  });
  return state.detail;
}

export function createReviewScenarioProxy({
  scenario = "passthrough",
  upstreamUrl = DEFAULT_UPSTREAM,
  listenHost = DEFAULT_LISTEN_HOST,
  listenPort = DEFAULT_LISTEN_PORT,
} = {}) {
  const upstream = assertLoopbackUrl(upstreamUrl, "upstream URL");
  const host = parseListenHost(listenHost);
  if (
    scenario !== "passthrough"
    && scenario !== "history-empty"
    && !RECOVERABLE_SCENARIOS.has(scenario)
    && !V2_TRANSIENT_SCENARIOS.has(scenario)
  ) {
    throw new Error(`unknown review scenario: ${scenario}`);
  }
  const injected = new Set();
  let v2State = null;
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
    const isV2Scenario = V2_TRANSIENT_SCENARIOS.has(scenario);
    const sessionPath = /^\/debates\/([^/]+)$/;
    const eventPath = /^\/debates\/([^/]+)\/events$/;
    const cancelPath = /^\/debates\/([^/]+)\/cancel$/;
    if (isV2Scenario && request.method === "POST" && parsedUrl.pathname === "/debates") {
      if (v2State) {
        jsonResponse(request, response, 409, {
          detail: "This local V2 review scenario supports one active Debate at a time.",
        });
        return;
      }
      try {
        const upstreamResult = await requestUpstreamJson(request, parsedUrl, upstream, body);
        if (upstreamResult.statusCode < 200 || upstreamResult.statusCode >= 300) {
          jsonResponse(request, response, upstreamResult.statusCode, upstreamResult.payload);
          return;
        }
        v2State = createV2State(upstreamResult.payload, scenario);
        jsonResponse(request, response, upstreamResult.statusCode, {
          ...v2State.detail,
          job_id: isRecord(upstreamResult.payload) && typeof upstreamResult.payload.job_id === "string"
            ? upstreamResult.payload.job_id
            : v2State.jobId,
        });
      } catch (error) {
        jsonResponse(request, response, 502, {
          detail: error instanceof Error ? error.message : "Could not prepare the local V2 review scenario.",
        });
      }
      return;
    }
    const detailMatch = sessionPath.exec(parsedUrl.pathname);
    const eventsMatch = eventPath.exec(parsedUrl.pathname);
    const cancelMatch = cancelPath.exec(parsedUrl.pathname);
    if (isV2Scenario && v2State && detailMatch && request.method === "GET" && detailMatch[1] === v2State.sessionId) {
      jsonResponse(request, response, 200, v2State.detail);
      return;
    }
    if (isV2Scenario && v2State && eventsMatch && request.method === "GET" && eventsMatch[1] === v2State.sessionId) {
      serveV2Events(request, response, v2State, parsedUrl);
      return;
    }
    if (isV2Scenario && v2State && cancelMatch && request.method === "POST" && cancelMatch[1] === v2State.sessionId) {
      if (scenario !== "v2-cancel") {
        jsonResponse(request, response, 409, { detail: "This local V2 scenario does not accept cancellation." });
        return;
      }
      jsonResponse(request, response, 202, cancelV2Scenario(v2State));
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
      if (v2State) {
        for (const subscriber of v2State.subscribers) subscriber.response.end();
        v2State.subscribers.clear();
      }
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
