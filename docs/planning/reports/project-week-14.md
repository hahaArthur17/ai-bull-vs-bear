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

## Follow-up — privacy-bounded standard Debate snapshot

The next Phase 6 slice adds a six-hour cache for only the normalized
`FactorSnapshot` used by a standard V2 request with `question=null`. The cache
key hashes the full immutable public `AnalysisContext` and ordered
factor-provider contract; no raw question, user identifier, Session ID, or
Message ID enters the key. A provider version or expected-category change
therefore creates a different entry.

Custom questions and non-empty top-level context metadata always return
`BYPASS`. Cache hits reuse factor collection only. Cross-user API tests prove
that each request still creates distinct canonical Sessions and Messages, and
generated Debate text is not cached. Invalid or mismatched cached snapshots are
discarded and recollected from the current canonical context.

The updated local gate is 291 backend tests, 11 mobile stream/view-state tests,
mobile TypeScript, and Expo Web export. The next Phase 6 slice is per-user
admission limits plus the one-active-Debate rule; distributed idempotency remains
separate.

## Follow-up — per-user Debate admission

Date: 2026-08-29

The third Phase 6 slice adds a configurable admission boundary before factor or
model work. It hashes user IDs in all coordination keys, checks the canonical
repository for non-terminal Sessions, atomically reserves one active slot, and
increments an expiring per-user counter. The safe defaults are one active
Debate and three new admissions per 3,600-second window.

Successful new requests expose `X-RateLimit-Limit` and
`X-RateLimit-Remaining`. An active Session returns `409`; exhausted capacity
returns `429` with a bounded `Retry-After`. A terminal canonical Session makes a
stale active-cache entry recoverable, so the 1,200-second coordination TTL is
never the authority. Sequential queued retries backed by the existing
deterministic Session/Job IDs do not consume a second slot.

The updated local gate is 296 backend tests, 11 mobile stream/view-state tests,
mobile TypeScript, and Expo Web export. The simultaneous distributed
idempotency lock is deliberately left for the next small commit; outage-level
API evidence and performance measurements remain before Phase 6 completion.
