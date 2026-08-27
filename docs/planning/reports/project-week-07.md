# Project Week 7 Report

Period: 2026-08-27

Status: Phase 1 in progress

## Goal

Begin the portfolio implementation plan without destabilizing the existing
synchronous analysis. Resolve when Supabase business tables and Queue objects
should be created, pin current behaviour, and establish the first extensible
factor boundary.

## Completed work

- Accepted a staged database decision: Phase 1 has no hosted DDL change, stock
  catalog changes belong to Phase 2, Debate tables to Phase 3, and `pgmq` Queue
  setup to Phase 5 (`7b4137c`).
- Added characterization tests for the current response/snapshot shape,
  user-owned history and watchlist behaviour, and validated model-provider
  inputs (`9374398`).
- Added immutable, JSON-safe `AnalysisContext`, `FactorObservation`, freshness,
  source-reference, snapshot, and `FactorProvider` contracts (`58c70f8`).
- Added `FactorRegistry` validation/failure handling and normalized the current
  indicator calculation behind `TechnicalFactorProvider` (`6b415a5`).
- Proved additive extension by registering a test-only mock sentiment provider
  without changing the registry or technical provider (`598eb3d`).

## Decisions

- Current Supabase tables remain the authority for the synchronous baseline but
  are not sufficient for the future multi-turn workflow.
- `public.debate_jobs` will be the canonical application ledger; extension-owned
  `pgmq` tables will carry delivery messages. They are intentionally separate.
- Field contracts are designed before DDL, while migrations wait until the
  owning phase can add RLS, indexes, idempotency, and isolation tests together.
- Generic factors are an orchestration boundary. Typed indicator API responses
  remain useful for charts and are not replaced with unstructured values.

## Verification

Focused checks passed after each change. The phase checkpoint uses:

```shell
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
cd apps/mobile && npm run typecheck
```

Result on 2026-08-27: 92 backend tests passed, mobile TypeScript passed, and all
local Markdown links resolved. The only backend warning remains the existing
Starlette/httpx test-client deprecation.

## Unfinished work

- Add normalized adapters for current macro, news, filing, and financial-fact
  inputs.
- Define Debate session, message, job, event, and repository contracts.
- Begin mobile screen/token extraction without changing visual behaviour.
- Do not apply Supabase DDL until the migration phase and its RLS tests are
  ready.

## Recommended next tasks

1. Extend `AnalysisContext` with typed current-source inputs and add the
   remaining factor adapters.
2. Define the Debate state/message/job/event contracts and transition tests.
3. Introduce Debate repository protocols before any Phase 3 migration.

## Related documents

- [`ADR-0001`](../../architecture/decisions/0001-staged-supabase-schema-and-queue.md)
- [`current-status.md`](../current-status.md)
- [`portfolio-implementation-plan.md`](../portfolio-implementation-plan.md)
- [`schema-plan.md`](../../database/schema-plan.md)
