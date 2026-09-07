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
