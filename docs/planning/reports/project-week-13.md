# Project Week 13 — Durable Debate Queue and Worker

Date: 2026-08-28

## Goal

Move the default-off V2 Debate from request-bound execution to a durable,
idempotent Queue/Worker path while preserving the legacy `/analysis` API,
zero-cost deployment defaults, generation-scoped cancellation, and canonical
Supabase persistence.

## Completed work

### Durable Queue transport and admission

- `c00dc13` adds the focused logged `pgmq` migration, identifier-only Queue
  payloads, transport repository contract, and in-memory/Supabase adapters.
- `1b3393e`, `2b29483`, and `b4c14a7` add the bounded Worker, deterministic
  snapshot serialization, and atomic idempotent Round 1 admission returning
  `202 Accepted`.
- `97127b0` runs bounded consumers in the FastAPI lifespan and adds the
  standalone `python -m app.debate_worker_main` entry point.

### Retry, crash recovery, and backpressure

- `f18ac80` classifies retryable Groq transport failures without exposing
  provider bodies and accepts only bounded `Retry-After` values.
- `022d655` and `c94c3c3` add validated Job/Session retry transitions and
  atomic Queue/ledger retry or exhausted-failure settlement.
- `3d94d4f` resumes a redelivered stage from its durable completed-turn prefix
  and preserves cumulative provider/token accounting.
- `2c6bca9` completes delayed retry, visibility-timeout recovery, terminal
  failure, and cancellation-after-crash handling.
- `fb5549c` repeatedly proves bounded backpressure: with two Workers and three
  submissions, only two sessions execute while the third remains queued.

### Queued Round 2 and visible state contracts

- `f240ce7` separates pure Challenge preparation from persistence.
- `b3c872b` atomically writes the Challenge intervention, User message, Session
  transition, Job, and Round 2 Queue message.
- `2c26702` makes queued Round 2 idempotent and completes the canonical
  13-message session through the Worker.
- `d340d40` exposes active Job detail plus retry/failure events.
- `a5c7688` tracks queued, running, retry, failed, cancelled, and terminal Job
  state in the mobile stream reducer.

## Key decisions

- Supabase remains canonical. `pgmq` owns delivery/visibility; the public
  `debate_jobs` table remains the application ledger.
- Queue payloads contain identifiers and safe trace metadata only. Workers
  reload protected context from the canonical tables after claim.
- One Render web process may run one bounded consumer for a free portfolio
  demo. The standalone entry point preserves a future separate-worker path.
- Redelivery resumes from complete persisted turns. Partial deltas are never
  canonical and are safe to discard after a crash.
- Redis is not used as Queue or persistence and remains a separate Phase 6
  optimization.

## Verification evidence

Latest full local gate at this milestone:

```text
backend: 276 passed, 1 existing Starlette/httpx deprecation warning
mobile stream reducer: 7 passed
mobile TypeScript: passed
Expo Web export: passed
```

Focused tests cover Queue SQL/grants, repository atomicity, duplicate
admission, API `202` contracts, bounded consumers, retry delay, visibility
redelivery, completed-turn resume, cancellation recovery, terminal failure,
Round 2 idempotency, and mobile Job-event reduction. Provider tests use fakes;
no live model quota was consumed.

## Deployment state and blockers

- `DEBATE_WORKFLOW_V2=false` and `DEBATE_QUEUE_ENABLED=false` remain the safe
  local/example/Render defaults.
- The catalog, Debate persistence, and Queue migrations have not been applied
  to hosted Supabase. Therefore no hosted Queue/RLS/restart claim is made.
- The event broker is process-local. Canonical messages survive a restart, but
  transient delta replay does not cross processes.
- The V2 stream client/reducer is implemented but not mounted in `App.tsx`, so
  visible queue status and mid-generation cancellation are not yet available in
  the classroom UI.

## Recommended next tasks

1. Mount a default-off V2 Debate screen that creates a queued Session, connects
   the stream client, renders Job states/drafts/canonical messages, and exposes
   generation-scoped cancellation.
2. Rerun TypeScript, reducer tests, Expo Web export, and the full backend suite;
   then record responsive Web evidence without enabling production flags.
3. After the UI gate, perform the controlled hosted database size/RLS/Queue
   migration and restart test before enabling any hosted V2 smoke path.

## Related documents

- [`current-status.md`](../current-status.md)
- [`portfolio-implementation-plan.md`](../portfolio-implementation-plan.md)
- [`api-contract.md`](../../api/api-contract.md)
- [`architecture overview`](../../architecture/overview.md)
- [`database schema plan`](../../database/schema-plan.md)
- [`live-services.md`](../../setup/live-services.md)

## Follow-up — visible V2 client integration

After the Queue milestone baseline above, `7fddcc1` added canonical Session
status to stream snapshots and raised the mobile state tests from 7 to 8.
`7be800d` then mounted a default-off dark financial-technology Debate screen
with:

- immediate `202` admission and stable client-generated idempotency keys;
- visible queued/running/retry/failure/settled states and safe reconnect;
- temporary streaming cards that cannot be mistaken for canonical messages;
- generation-scoped cancellation while a Job is active;
- six Round 1 Bull/Bear messages, Interim Judge pause, exact-passage Challenge
  input, queued Round 2, and the 13-message Final Judge result; and
- an explicit mobile `demo` Auth mode for credential-free local verification,
  while Render fixes production Auth to `supabase` and V2 UI to `false`.

The updated gate is 276 backend tests, 11 mobile stream/view-state tests,
TypeScript, and Expo Web export. A real local browser run observed `202` for
both rounds, live draft-to-canonical replacement, desktop and 390px layouts,
and no console warnings/errors. This local evidence does not replace the
pending hosted Supabase migration/RLS/restart check.
