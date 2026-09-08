import assert from "node:assert/strict";
import http from "node:http";
import { test } from "node:test";

import { createReviewScenarioProxy } from "./review-scenario-proxy.mjs";

function requestJson(port, path, { method = "GET", body, origin = "http://127.0.0.1:8081" } = {}) {
  return new Promise((resolve, reject) => {
    const payload = body === undefined ? null : JSON.stringify(body);
    const request = http.request({
      hostname: "127.0.0.1",
      port,
      path,
      method,
      headers: {
        Origin: origin,
        ...(payload ? { "content-type": "application/json", "content-length": Buffer.byteLength(payload) } : {}),
      },
    }, (response) => {
      const chunks = [];
      response.on("data", (chunk) => chunks.push(chunk));
      response.on("end", () => resolve({
        status: response.statusCode,
        headers: response.headers,
        body: JSON.parse(Buffer.concat(chunks).toString("utf8")),
      }));
    });
    request.on("error", reject);
    if (payload) request.write(payload);
    request.end();
  });
}

function requestSse(port, path, { eventCount } = {}) {
  return new Promise((resolve, reject) => {
    const events = [];
    let pending = "";
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };
    const request = http.request({
      hostname: "127.0.0.1",
      port,
      path,
      method: "GET",
      headers: { accept: "text/event-stream" },
    }, (response) => {
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        pending += chunk;
        const frames = pending.split("\n\n");
        pending = frames.pop();
        for (const frame of frames) {
          const dataLine = frame.split("\n").find((line) => line.startsWith("data: "));
          if (dataLine) events.push(JSON.parse(dataLine.slice(6)));
        }
        if (eventCount !== undefined && events.length >= eventCount) {
          finish({ status: response.statusCode, events });
          request.destroy();
          response.destroy();
        }
      });
      response.on("end", () => finish({ status: response.statusCode, events }));
      response.on("error", (error) => {
        if (!settled) reject(error);
      });
    });
    request.on("error", (error) => {
      if (!settled) reject(error);
    });
    request.end();
  });
}

const V2_IDS = {
  session: "11111111-1111-4111-8111-111111111111",
  generation: "22222222-2222-4222-8222-222222222222",
  job: "33333333-3333-4333-8333-333333333333",
};

function reviewFixtureDebateDetail() {
  const now = "2026-09-08T00:00:00.000Z";
  return {
    session: {
      id: V2_IDS.session,
      ticker: "AAPL",
      status: "queued_round_1",
      active_branch_id: "55555555-5555-4555-8555-555555555555",
      active_generation_id: V2_IDS.generation,
      opening_side: "bull",
      initial_question: null,
      created_at: now,
      updated_at: now,
      completed_at: null,
      interim_judge_message_id: null,
      final_judge_message_id: null,
      safe_error_code: null,
    },
    messages: [{
      id: "66666666-6666-4666-8666-666666666666",
      role: "system",
      content: "The real fixture response is replaced for visual review.",
      created_at: now,
    }],
    job: {
      id: V2_IDS.job,
      session_id: V2_IDS.session,
      job_type: "round_1",
      status: "queued",
      attempt_count: 0,
      max_attempts: 3,
      safe_error_code: null,
      created_at: now,
      updated_at: now,
      started_at: null,
      finished_at: null,
    },
    job_id: V2_IDS.job,
    execution_mode: "synchronous_preview",
  };
}

function v2FixtureUpstream(request, response) {
  assert.equal(request.method, "POST");
  assert.equal(request.url, "/debates");
  response.writeHead(201, { "content-type": "application/json" });
  response.end(JSON.stringify(reviewFixtureDebateDetail()));
}

function assertContinuous(events, startAt = 1) {
  assert.deepEqual(events.map((event) => event.sequence), events.map((_event, index) => startAt + index));
  for (const event of events) {
    assert.equal(event.version, 1);
    assert.equal(event.session_id, V2_IDS.session);
    assert.match(event.event_id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  }
}

function assertStableV2Metadata(events) {
  for (const event of events) {
    assert.equal(event.timestamp, `2026-09-08T00:00:0${event.sequence}.000Z`);
  }
}

async function withUpstream(handler, callback) {
  const upstream = http.createServer((request, response) => {
    if (request.url === "/health") {
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify({ data_mode: "review_fixture" }));
      return;
    }
    handler(request, response);
  });
  await new Promise((resolve) => upstream.listen(0, "127.0.0.1", resolve));
  const address = upstream.address();
  const proxy = createReviewScenarioProxy({
    upstreamUrl: `http://127.0.0.1:${address.port}`,
    listenHost: "127.0.0.1",
    listenPort: 0,
    scenario: callback.scenario,
  });
  const proxyAddress = await proxy.listen();
  try {
    await callback.run(proxyAddress.port);
  } finally {
    await proxy.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
}

for (const scenario of [
  ["watchlist-recover", "GET", "/watchlist"],
  ["search-recover", "GET", "/stocks?q=Apple"],
  ["bundle-recover", "GET", "/stocks/AAPL/bundle"],
  ["examination-recover", "POST", "/claims/claim-1/examine"],
  ["explanation-recover", "POST", "/debates/debate-1/explanations"],
]) {
  test(`${scenario[0]} injects one failure and then passes through`, async () => {
    await withUpstream((request, response) => {
      response.writeHead(200, {
        "content-type": "application/json",
        "x-upstream": "yes",
      });
      response.end(JSON.stringify({ ok: true, path: request.url }));
    }, {
      scenario: scenario[0],
      run: async (port) => {
        const first = await requestJson(port, scenario[2], {
          method: scenario[1],
          body: scenario[1] === "POST" ? { question: "review" } : undefined,
        });
        assert.equal(first.status, 503);
        assert.match(first.body.detail, /recoverable error/);
        assert.equal(first.headers["access-control-allow-origin"], "http://127.0.0.1:8081");

        const second = await requestJson(port, scenario[2], {
          method: scenario[1],
          body: scenario[1] === "POST" ? { question: "review" } : undefined,
        });
        assert.equal(second.status, 200);
        assert.deepEqual(second.body, { ok: true, path: scenario[2] });
        assert.equal(second.headers["x-upstream"], "yes");
      },
    });
  });
}

test("history-empty returns a stable empty state without contacting upstream", async () => {
  let upstreamCalls = 0;
  await withUpstream((_request, response) => {
    upstreamCalls += 1;
    response.writeHead(500);
    response.end("should not be called");
  }, {
    scenario: "history-empty",
    run: async (port) => {
      const first = await requestJson(port, "/analysis");
      const second = await requestJson(port, "/analysis");
      const debates = await requestJson(port, "/debates?limit=50");
      assert.equal(first.status, 200);
      assert.deepEqual(first.body, []);
      assert.deepEqual(second.body, []);
      assert.deepEqual(debates.body, []);
      assert.equal(upstreamCalls, 0);
    },
  });
});

test("v2-reconnect provides a deterministic first disconnect and a recoverable second stream", async () => {
  await withUpstream(v2FixtureUpstream, {
    scenario: "v2-reconnect",
    run: async (port) => {
      const created = await requestJson(port, "/debates", { method: "POST", body: { ticker: "AAPL" } });
      assert.equal(created.status, 201);
      assert.equal(created.body.session.status, "running_round_1");
      assert.equal(created.body.job.status, "running");
      assert.deepEqual(created.body.messages, []);

      const initial = await requestSse(port, `/debates/${V2_IDS.session}/events`);
      assert.equal(initial.status, 200);
      assert.deepEqual(initial.events.map((event) => event.type), ["job.started"]);
      assertContinuous(initial.events);
      assertStableV2Metadata(initial.events);
      assert.equal(initial.events[0].payload.attempt_count, 1);

      const recovered = await requestSse(port, `/debates/${V2_IDS.session}/events?after_sequence=1`, { eventCount: 1 });
      assert.equal(recovered.status, 200);
      assert.deepEqual(recovered.events.map((event) => event.type), ["job.started"]);
      assertContinuous(recovered.events, 2);
      assertStableV2Metadata(recovered.events);
      assert.equal(recovered.events[0].payload.attempt_count, 2);

      const detail = await requestJson(port, `/debates/${V2_IDS.session}`);
      assert.equal(detail.status, 200);
      assert.equal(detail.body.session.status, "running_round_1");
      assert.equal(detail.body.job.status, "running");
      assert.equal(detail.body.job.attempt_count, 2);
      assert.deepEqual(detail.body.messages, []);
    },
  });
});

test("v2-retry exposes a queued retry detail and an ordered retry event", async () => {
  await withUpstream(v2FixtureUpstream, {
    scenario: "v2-retry",
    run: async (port) => {
      const created = await requestJson(port, "/debates", { method: "POST", body: { ticker: "AAPL" } });
      assert.equal(created.status, 201);
      assert.equal(created.body.session.status, "queued_round_1");
      assert.equal(created.body.job.status, "queued");
      assert.equal(created.body.job.attempt_count, 1);

      const stream = await requestSse(port, `/debates/${V2_IDS.session}/events`, { eventCount: 1 });
      assert.equal(stream.status, 200);
      assert.deepEqual(stream.events.map((event) => event.type), ["job.retry_scheduled"]);
      assertContinuous(stream.events);
      assert.equal(stream.events[0].payload.generation_id, V2_IDS.generation);
      assert.equal(stream.events[0].payload.retry_delay_seconds, 4);
      assert.equal(stream.events[0].payload.job_type, "round_1");
      assertStableV2Metadata(stream.events);

      const detail = await requestJson(port, `/debates/${V2_IDS.session}`);
      assert.equal(detail.body.session.status, "queued_round_1");
      assert.equal(detail.body.job.status, "queued");
      assert.equal(detail.body.job.id, V2_IDS.job);
    },
  });
});

test("v2-failure keeps GET detail and the terminal SSE sequence consistent", async () => {
  await withUpstream(v2FixtureUpstream, {
    scenario: "v2-failure",
    run: async (port) => {
      const created = await requestJson(port, "/debates", { method: "POST", body: { ticker: "AAPL" } });
      assert.equal(created.body.session.status, "running_round_1");

      const stream = await requestSse(port, `/debates/${V2_IDS.session}/events`);
      assert.equal(stream.status, 200);
      assert.deepEqual(stream.events.map((event) => event.type), ["job.started", "job.failed", "session.failed"]);
      assertContinuous(stream.events);
      assert.equal(stream.events[1].payload.generation_id, V2_IDS.generation);
      assert.equal(stream.events[1].payload.safe_error_code, "review_fixture_failure");
      assert.equal(stream.events[2].payload.job_id, V2_IDS.job);
      assertStableV2Metadata(stream.events);

      const detail = await requestJson(port, `/debates/${V2_IDS.session}`);
      assert.equal(detail.body.session.status, "failed");
      assert.equal(detail.body.job.status, "failed");
      assert.equal(detail.body.session.safe_error_code, "review_fixture_failure");
      assert.deepEqual(detail.body.messages, []);
    },
  });
});

test("v2-cancel returns cancelled detail and does not persist a valid late draft", async () => {
  await withUpstream(v2FixtureUpstream, {
    scenario: "v2-cancel",
    run: async (port) => {
      const created = await requestJson(port, "/debates", { method: "POST", body: { ticker: "AAPL" } });
      assert.equal(created.body.session.status, "running_round_1");

      const started = await requestSse(port, `/debates/${V2_IDS.session}/events`, { eventCount: 1 });
      assert.deepEqual(started.events.map((event) => event.type), ["job.started"]);
      assertContinuous(started.events);

      const cancelled = await requestJson(port, `/debates/${V2_IDS.session}/cancel`, { method: "POST" });
      assert.equal(cancelled.status, 202);
      assert.equal(cancelled.body.session.status, "cancelled");
      assert.equal(cancelled.body.job.status, "cancelled");
      assert.notEqual(cancelled.body.session.active_generation_id, V2_IDS.generation);
      assert.deepEqual(cancelled.body.messages, []);

      const lateEvents = await requestSse(port, `/debates/${V2_IDS.session}/events?after_sequence=1`, { eventCount: 4 });
      assert.deepEqual(lateEvents.events.map((event) => event.type), [
        "session.cancel_requested",
        "session.cancelled",
        "turn.started",
        "turn.delta",
      ]);
      assertContinuous(lateEvents.events, 2);
      assert.equal(lateEvents.events[0].payload.cancelled_generation_id, V2_IDS.generation);
      assert.equal(lateEvents.events[0].payload.generation_id, cancelled.body.session.active_generation_id);
      assert.equal(lateEvents.events[1].payload.generation_id, cancelled.body.session.active_generation_id);
      assert.equal(lateEvents.events[2].payload.generation_id, V2_IDS.generation);
      assert.equal(lateEvents.events[3].payload.generation_id, V2_IDS.generation);
      assert.equal(lateEvents.events[2].payload.message_id, lateEvents.events[3].payload.message_id);
      assertStableV2Metadata(lateEvents.events);

      const detail = await requestJson(port, `/debates/${V2_IDS.session}`);
      assert.equal(detail.body.session.status, "cancelled");
      assert.deepEqual(detail.body.messages, []);
      assert.doesNotMatch(JSON.stringify(detail.body), /Late simulated output/);

      const repeated = await requestJson(port, `/debates/${V2_IDS.session}/cancel`, { method: "POST" });
      assert.equal(repeated.status, 202);
      assert.deepEqual(repeated.body, cancelled.body);
    },
  });
});

test("V2 scenarios admit one fixture Debate and never create another upstream Debate", async () => {
  let createCalls = 0;
  await withUpstream((request, response) => {
    if (request.method === "POST" && request.url === "/debates") {
      createCalls += 1;
      response.writeHead(201, { "content-type": "application/json" });
      response.end(JSON.stringify(reviewFixtureDebateDetail()));
      return;
    }
    response.writeHead(404, { "content-type": "application/json" });
    response.end(JSON.stringify({ detail: "unexpected request" }));
  }, {
    scenario: "v2-retry",
    run: async (port) => {
      const first = await requestJson(port, "/debates", { method: "POST", body: { ticker: "AAPL" } });
      const repeated = await requestJson(port, "/debates", { method: "POST", body: { ticker: "MSFT" } });
      assert.equal(first.status, 201);
      assert.equal(repeated.status, 409);
      assert.match(repeated.body.detail, /one active Debate/);
      assert.equal(createCalls, 1);
    },
  });
});

test("proxy rejects non-loopback upstreams and listen hosts", () => {
  assert.throws(
    () => createReviewScenarioProxy({ upstreamUrl: "http://example.com:8000" }),
    /loopback host/,
  );
  assert.throws(
    () => createReviewScenarioProxy({ listenHost: "0.0.0.0" }),
    /listen host/,
  );
  assert.throws(
    () => createReviewScenarioProxy({ upstreamUrl: "http://user:secret@127.0.0.1:8000" }),
    /must not contain credentials/,
  );
});

test("proxy does not grant CORS access to a non-local webpage", async () => {
  await withUpstream((_request, response) => {
    response.writeHead(200, {
      "content-type": "application/json",
      "access-control-allow-origin": "*",
      "access-control-allow-credentials": "true",
    });
    response.end(JSON.stringify({ ok: true }));
  }, {
    scenario: "passthrough",
    run: async (port) => {
      const response = await requestJson(port, "/stocks", { origin: "https://example.com" });
      assert.equal(response.status, 200);
      assert.equal(response.headers["access-control-allow-origin"], undefined);
      assert.equal(response.headers["access-control-allow-credentials"], undefined);
    },
  });
});

test("proxy fails closed if its running upstream stops being a review fixture", async () => {
  let dataMode = "review_fixture";
  let businessCalls = 0;
  const upstream = http.createServer((request, response) => {
    response.writeHead(200, { "content-type": "application/json" });
    if (request.url === "/health") {
      response.end(JSON.stringify({ data_mode: dataMode }));
      return;
    }
    businessCalls += 1;
    response.end(JSON.stringify({ ok: true }));
  });
  await new Promise((resolve) => upstream.listen(0, "127.0.0.1", resolve));
  const address = upstream.address();
  const proxy = createReviewScenarioProxy({
    upstreamUrl: `http://127.0.0.1:${address.port}`,
    listenPort: 0,
  });
  const proxyAddress = await proxy.listen();
  try {
    dataMode = "standard";
    const response = await requestJson(proxyAddress.port, "/stocks");
    assert.equal(response.status, 502);
    assert.match(response.body.detail, /not an isolated review fixture/);
    assert.equal(businessCalls, 0);
  } finally {
    await proxy.close();
    await new Promise((resolve) => upstream.close(resolve));
  }
});

test("proxy refuses an upstream that is not the isolated review fixture", async () => {
  const upstream = http.createServer((_request, response) => {
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ data_mode: "standard" }));
  });
  await new Promise((resolve) => upstream.listen(0, "127.0.0.1", resolve));
  const address = upstream.address();
  const proxy = createReviewScenarioProxy({
    upstreamUrl: `http://127.0.0.1:${address.port}`,
    listenPort: 0,
  });
  try {
    await assert.rejects(() => proxy.listen(), /data_mode=review_fixture/);
  } finally {
    await new Promise((resolve) => upstream.close(resolve));
  }
});
