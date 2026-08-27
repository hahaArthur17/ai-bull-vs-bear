# Project Week 8 Report

Period: 2026-08-27

Status: Phase 3 complete in code; hosted database gates remain

## Goal

Implement zero-call stock discovery and the complete deterministic Debate
domain without changing the deployed single-response baseline. Prepare, but do
not apply, the Supabase schema needed by later Queue and streaming phases.

## Completed work

- Added and verified a bounded 7,695-row SEC identity catalog, ranked search,
  explicit coverage, Watchlist-only symbols, and mobile coverage gates.
- Added five canonical Debate tables, owner-read RLS, service-only writes, and
  transactional Session/Job and Message/citation functions as checked-in
  migrations.
- Implemented matching in-memory and Supabase repositories with immutable
  snapshot, optimistic-state, atomicity, idempotency, and owner-isolation
  checks.
- Implemented six mutually aware Round 1 turns plus Interim Judge, a persisted
  user Challenge, four Round 2 turns plus Final Judge, and safe partial-failure
  handling.
- Added `DEBATE_WORKFLOW_V2=false` as the application, test, example, and Render
  default (`3c921b6`).
- Added the synchronous Phase 3 preview service (`e0635e0`) and authenticated
  Session, Message, and Challenge routes (`6f6d0d7`).
- Kept `/analysis` unchanged and proved it works with V2 both disabled and
  enabled.

## Preview contract and boundary

The enabled preview persists complete canonical messages and citations and
returns `synchronous_preview` after each deterministic stage finishes. It does
not claim to stream, enqueue, retry across processes, or use a live model. When
disabled it returns `404` and is omitted from OpenAPI. Production remains
disabled.

## Verification

```shell
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd apps/mobile && npm run build:web
cd apps/mobile && npm run typecheck
```

Result on 2026-08-27: 190 backend tests passed. The only warning is the existing
Starlette/httpx test-client deprecation. Expo Web export and the mobile
TypeScript check also passed. API tests prove the three Round 1 exchanges,
Interim Judge pause, Challenge-driven Round 2, Final Judge, coverage gate,
owner isolation, invalid-target safety, and legacy compatibility.

## Hosted state and blocker

Catalog and Debate migrations are committed but not applied to hosted
Supabase. The workspace has application API keys but no safe database management
connection in this environment. Before enabling V2 in Supabase mode, the owner
must run the documented database-size preflight, apply migrations in filename
order, measure the catalog relation, and verify public-read plus two-user and
service-role access. No Queue or Redis migration should bypass that gate.

## Recommended next tasks

1. Begin Phase 4 with a bounded per-turn provider adapter and compatibility
   tests; retain the deterministic provider for zero-cost replay.
2. Add an in-process versioned event broker/SSE preview, including heartbeat,
   reconnect from canonical messages, and late-generation rejection.
3. Apply the hosted catalog and Debate migrations only when safe management
   access is available; keep production V2 disabled until verification passes.

## Related documents

- [`API contract`](../../api/api-contract.md)
- [`architecture overview`](../../architecture/overview.md)
- [`current status`](../current-status.md)
- [`portfolio implementation plan`](../portfolio-implementation-plan.md)
- [`free deployment guide`](../../setup/free-deployment.md)
