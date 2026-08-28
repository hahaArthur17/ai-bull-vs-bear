# Weekly Reports

Weekly reports are the append-only project memory. Put implementation detail,
verification evidence, blockers, and handoff notes in one report per project
week. Do not use a historical report as the current operating plan.

## Context recovery order

When resuming the project:

1. read the [planning index](../README.md) and
   [current status](../current-status.md);
2. read the [project issue log](../issue-log.md) for unresolved risks and
   prior incident evidence;
3. read the latest report in this folder;
4. open the active
   [`portfolio-implementation-plan.md`](../portfolio-implementation-plan.md);
5. open only the architecture/setup documents relevant to the selected task;
   and
6. compare the repository state and passing tests with the documentation before
   choosing work.

## Reports

- [`project-week-04.md`](project-week-04.md) — authentication, persistence,
  live evidence, vector retrieval, and live-price cache implementation.
- [`project-week-05.md`](project-week-05.md) — vectorization research,
  multi-profile storage, source-aware chunking, XBRL facts, and release checks.
- [`project-week-06.md`](project-week-06.md) — current-price Debate integrity,
  interactive charts, and the first cached macro-market context layer.
- [`project-week-07.md`](project-week-07.md) — staged Supabase/Queue decision,
  Phase 1 characterization, and the extensible factor foundation.
- [`project-week-08.md`](project-week-08.md) — zero-cost catalog implementation,
  Debate persistence, deterministic two-round orchestration, and the default-off
  V2 preview API.
- [`project-week-09.md`](project-week-09.md) — bounded Debate event broker,
  orchestration events, and resumable authenticated SSE preview.
- [`project-week-10.md`](project-week-10.md) — async per-Turn provider contract,
  compatibility/native deterministic adapters, and validated stream
  persistence.
- [`project-week-11.md`](project-week-11.md) — default-off live Groq Turn
  streaming, current model migration, and the resumable mobile SSE client.
- [`project-week-12.md`](project-week-12.md) — generation-scoped cancellation,
  atomic late-write prevention, and mobile stale-output rejection.
- [`project-week-13.md`](project-week-13.md) — durable Supabase Queue transport,
  bounded Workers, retry/redelivery recovery, and the mounted default-off V2
  Debate experience.

## Template for a new report

- goal and dates;
- completed work with commit IDs;
- live state and verification commands/results;
- decisions and why they were made;
- unfinished work, exact blocker, and required owner action;
- recommended next three tasks; and
- links to changed architecture/setup documents.

Never include passwords, API keys, JWTs, service-role keys, private email
addresses, or screenshots containing credentials.
