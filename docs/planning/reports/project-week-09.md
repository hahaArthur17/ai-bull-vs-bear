# Project Week 9 Report

Period: 2026-08-28

Status: Phase 4 streaming foundation in progress

## Goal

Establish a zero-cost, owner-scoped streaming boundary without claiming that
the synchronous deterministic provider, local process memory, or disabled
production route is a durable live-model stream.

## Completed work

- Added a thread-safe process-local event broker with per-Session monotonic
  sequences, blocking wait, resume replay, unbuffered heartbeats, and explicit
  event/session capacity (`03627b5`).
- Added safe cursor-expiration behavior and SSE frame serialization. Heartbeats
  do not advance the resume cursor.
- Made the orchestrator publish Job, Turn, buffered delta, citation, Judge,
  safe-failure, and terminal Session events (`cfac90d`).
- Kept complete validated messages/citations canonical. A transient broker
  failure is logged but cannot prevent the Debate workflow from completing.
- Labelled deterministic text chunks `source=buffered_preview`; tests reconstruct
  the canonical message exactly and prevent whitespace loss at chunk boundaries.
- Added the authenticated `GET /debates/{session_id}/events` SSE preview with
  owner isolation, `after_sequence`, `Last-Event-ID`, heartbeat, terminal close,
  cache/buffering headers, and `409` canonical-reload guidance for expired
  cursors (`82e2374`).

## Verification

```shell
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd apps/mobile && npm run build:web
cd apps/mobile && npm run typecheck
```

Result on 2026-08-28: 207 backend tests, Expo Web export, and mobile TypeScript
passed. The sole backend warning remains the existing Starlette/httpx
test-client deprecation.

## Honest capability boundary

The current `POST /debates` still finishes deterministic generation before the
client can attach. Its SSE endpoint therefore proves framing, ordered replay,
cursor resume, heartbeat, isolation, and canonical recovery—not concurrent
provider token streaming. The buffer is intentionally process-local and
bounded; complete database messages are the recovery source after restart or
cursor expiry.

Production remains `DEBATE_WORKFLOW_V2=false`, and no hosted migration, Queue,
Redis, provider quota, or additional deployment resource was used.

## Recommended next tasks

1. Define an async per-turn stream provider contract and a compatibility adapter
   for whole-draft providers.
2. Implement one live provider adapter behind explicit configuration with fully
   mocked automated tests and bounded output/token use.
3. Add a fetch-based Web/React Native `DebateStreamClient` that loads canonical
   messages first, parses SSE centrally, reconnects with the last sequence, and
   ignores stale generation IDs.

## Related documents

- [`API contract`](../../api/api-contract.md)
- [`agent workflow`](../../agents/agent-workflow.md)
- [`architecture overview`](../../architecture/overview.md)
- [`current status`](../current-status.md)
- [`portfolio implementation plan`](../portfolio-implementation-plan.md)
