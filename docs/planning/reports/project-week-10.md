# Project Week 10 Report

Period: 2026-08-28

Status: Phase 4 async provider boundary complete; live adapter pending

## Goal

Separate the existing whole-draft preview from a genuine async per-Turn
Provider boundary, and prove that partial or invalid streamed output can never
be mistaken for a complete canonical Debate message.

## Completed work

- Added immutable delta, completion, finish-reason, and token-usage contracts
  plus a structural async Provider protocol (`5209db1`).
- Added a collector that enforces contiguous chunks, a normal completion,
  byte-equivalent reconstructed text, the request output limit, latest-opponent
  target, and frozen evidence IDs before returning a persistable draft.
- Preserved meaningful leading/trailing whitespace in Provider deltas and
  versioned event payloads.
- Added `WholeDraftTurnStreamAdapter`, which executes a blocking legacy
  Provider off the event-loop thread and labels the result
  `buffered_compatibility` (`cfc5dfa`).
- Added a zero-token `DeterministicStreamingDebateProvider` for native async
  contract tests without external credentials or quota.
- Added `execute_job_streaming`, which publishes arriving deltas, persists only
  a validated completed Turn, aggregates Turn token usage, retains the existing
  Judge boundary, and preserves safe terminal failures (`149a7ed`).
- Proved a stream interruption leaves no incomplete message, does not expose
  private Provider failure data, and records only the safe Session/Job code.

## Verification

```shell
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd apps/mobile && npm run build:web
cd apps/mobile && npm run typecheck
```

Result on 2026-08-28: 223 backend tests passed. The sole warning remains the
existing Starlette/httpx test-client deprecation. Expo Web export and the
mobile TypeScript check also passed.

## Honest capability boundary

The async orchestration path is implemented and tested but is not selected by
the current HTTP creation route. The enabled preview still uses the
whole-draft compatibility path, and production remains V2-disabled. No Groq or
Gemini request, token quota, Queue, Redis service, hosted migration, or new
deployment resource was used.

## Recommended next tasks

1. Choose one live streaming provider after revalidating its current API and
   free quota; implement it only behind explicit configuration and mocks.
2. Add a start mode that can run async generation concurrently with the SSE
   consumer while clearly labelling its non-durable pre-Queue limitation.
3. Implement the fetch-based Web/React Native stream client with canonical
   preload, centralized parsing, resume sequence, and generation filtering.

## Related documents

- [`API contract`](../../api/api-contract.md)
- [`agent workflow`](../../agents/agent-workflow.md)
- [`architecture overview`](../../architecture/overview.md)
- [`current status`](../current-status.md)
- [`portfolio implementation plan`](../portfolio-implementation-plan.md)
