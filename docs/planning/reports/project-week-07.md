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
- Added typed immutable inputs for evidence, macro observations, and structured
  financial facts, plus a pure snapshot factory with no database/network reads
  (`f689328`).
- Added Macro, News, Filing, and Financial Facts providers and a factory for the
  complete current-source registry (`191f65c`).
- Added immutable Debate session/message/intervention contracts and exact
  round-one/round-two turn plans (`ab206bf`).
- Added the single legal session-state transition service with Judge,
  cancellation, failure, and terminal-state tests (`2183974`).
- Added job-ledger, identifier-only Queue payload, and versioned safe event
  contracts (`4831b22`).
- Added database-independent Session/Job repository and atomic unit-of-work
  protocols (`554118f`).
- Added grounded turn/Judge request, draft, and provider protocols that require
  the latest opponent message as the rebuttal target (`22bacd3`).

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

Result on 2026-08-27: 123 backend tests passed, mobile TypeScript passed, and all
local Markdown links resolved. The only backend warning remains the existing
Starlette/httpx test-client deprecation.

## Unfinished work

- Begin mobile screen/token extraction without changing visual behaviour.
- Do not apply Supabase DDL until the migration phase and its RLS tests are
  ready.

## Recommended next tasks

1. Begin extracting mobile screens and shared tokens without changing visual
   behaviour.
2. Complete the Phase 1 compatibility gate and documentation checkpoint.
3. Start Phase 2 catalog-source selection only after Phase 1 is marked done.

## Related documents

- [`ADR-0001`](../../architecture/decisions/0001-staged-supabase-schema-and-queue.md)
- [`current-status.md`](../current-status.md)
- [`portfolio-implementation-plan.md`](../portfolio-implementation-plan.md)
- [`schema-plan.md`](../../database/schema-plan.md)
