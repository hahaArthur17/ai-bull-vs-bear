# Project Week 14 — Redis Foundation and Public Stock Response Cache

Date: 2026-08-28

Status: Phase 6 in progress; first hot-read slice complete locally

## Goal

Start Phase 6 without changing canonical persistence: add a failure-safe cache
boundary, cache only public stock reads, and reduce the mobile stock-detail
fan-out while keeping the current quote fresh.

## Completed work

- `7058acd` adds local and Redis TTL values, owner locks, expiring counters,
  strict Redis timeouts, safe configuration validation, health state, and a
  process-local outage fallback.
- The response-cache slice adds privacy-safe hashed stock-search keys with a
  30-minute TTL and versioned stock-bundle keys with a five-minute TTL.
- `GET /stocks/{ticker}/bundle` returns the public detail payload in one call;
  the mobile client now uses it instead of seven parallel requests.
- The optional current quote is fetched after the cache read and is never
  stored in the bundle cache.
- `X-Cache-Status` and in-process counters distinguish `HIT`, `MISS`, `BYPASS`,
  and `DEGRADED` without exposing cache-key contents.

## Verification

The local gate for this slice is:

```text
backend: 284 passed, 1 existing Starlette/httpx deprecation warning
mobile stream/view-state tests: 11 passed
mobile TypeScript: passed
Expo Web export: passed
```

Focused tests prove a repeat catalog search and stock-bundle read avoid another
repository call, catalog-only bundles remain rejected, cache keys do not expose
raw queries, and a bundle cache hit still resolves a fresh quote.

## Boundaries and remaining work

- Redis remains disabled by default and is not canonical persistence or Queue
  transport.
- No arbitrary user question or personal identity value is stored in these
  cache keys; the bundle key contains only the public ticker and data version.
- Standard-Debate snapshot caching is the next planned slice.
- Per-user rate limits, the one-active-Debate rule, distributed idempotency
  wiring, whole-API outage proof, and before/after measurements remain before
  Phase 6 can be marked done.

## Recommended next task

Add a standard-question Debate snapshot cache keyed only by the immutable
factor/evidence snapshot and versioned provider contract. Keep arbitrary user
questions and personalized context outside shared cache entries.

## Related documents

- [`current-status.md`](../current-status.md)
- [`portfolio-implementation-plan.md`](../portfolio-implementation-plan.md)
- [`api-contract.md`](../../api/api-contract.md)
- [`architecture overview`](../../architecture/overview.md)
- [`live-services.md`](../../setup/live-services.md)
