# Project Week 12 Report

Period: 2026-08-28

Status: Phase 4 cancellation boundary complete; Queue integration next

## Goal

Let a user cancel one expected Debate generation without allowing delayed
provider output to become canonical, corrupt Job/Session state, or reappear in
the mobile stream.

## Completed work

- Added deterministic generation invalidation and explicit queued/running Job
  cancellation state (`4caa46c`). Both persistence adapters now expose the one
  active Job for a Session, and the migration enforces that invariant with a
  partial unique index.
- Strengthened complete-message persistence (`4caa46c`). The in-memory adapter
  and service-only Supabase RPC reject inactive branches, invalid generations,
  cancelling/terminal Sessions, and the wrong running round. The RPC locks the
  Session row before the decision; already stored identical messages remain
  idempotent.
- Added orchestrator cancellation settlement (`ca9cf45`). Queued Jobs cancel
  immediately. Running generation code polls canonical state around deltas,
  Judge calls, and persistence; cancellation has a separate control path and
  cannot be rewritten as `session.failed`.
- Added a controlled concurrency test (`ca9cf45`) that pauses a provider after
  its first delta, accepts cancellation, then releases late output. It proves
  zero message persistence, a cancelled Job and Session, and no completion or
  failure event.
- Added the owner-scoped `POST /debates/{session_id}/cancel` contract with an
  expected `generation_id`, idempotent accepted response, ownership isolation,
  and stale-generation conflict (`9f772cf`).
- Added `api.cancelDebate` and cancellation-aware mobile reduction (`9f772cf`).
  `session.cancel_requested` rotates client generation and clears drafts;
  subsequent old-generation deltas advance only the event cursor.

## Verification

```shell
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
(cd apps/mobile && npm run typecheck)
(cd apps/mobile && npm run test:stream)
(cd apps/mobile && npm run build:web)
```

Result on 2026-08-28: 239 backend tests and 6 mobile stream tests passed. The
mobile TypeScript check and Expo Web export passed. The only backend warning is
the existing Starlette/httpx test-client deprecation.

No live provider request was made, no external quota was consumed, and no
hosted Supabase migration was applied. Production remains
`DEBATE_WORKFLOW_V2=false` with deterministic streaming selected.

## Decisions

- A cancel request includes the generation observed by the client. This stops a
  stale screen from cancelling a newer round.
- Cancellation first rotates `active_generation_id`; transport-level provider
  cancellation is an optimisation, while canonical persistence is the safety
  boundary.
- A running request may temporarily return `cancel_requested`. It settles at
  the next executor check because a remote provider call cannot always be
  forcibly stopped.
- Partial deltas stay transient. Cancellation does not persist an incomplete
  message merely to record what the provider had emitted.

## Honest capability boundary

The default-off synchronous preview exposes the cancellation contract, but
`POST /debates` still returns only after Round 1 finishes. Therefore the current
mobile screen cannot yet initiate useful mid-generation cancellation. Supabase
Queue/Worker start semantics must return the Session first; only then should
the stream client and cancel action be mounted in `App.tsx`.

## Recommended next tasks

1. Add the focused Supabase Queue migration and identifier-only queue payload.
2. Implement an idempotent bounded Worker claim/execute/ack lifecycle with
   crash and redelivery tests.
3. Change the V2 create route to queued acceptance, then mount the existing
   stream and cancellation client paths in an extracted Debate screen.

## Related documents

- [API contract](../../api/api-contract.md)
- [architecture overview](../../architecture/overview.md)
- [database schema plan](../../database/schema-plan.md)
- [agent workflow](../../agents/agent-workflow.md)
- [current status](../current-status.md)
- [portfolio implementation plan](../portfolio-implementation-plan.md)
