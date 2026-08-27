# ADR-0001: Stage Supabase Schema and Queue Migrations

Date: 2026-08-27

Status: Accepted

## Context

The implemented Supabase schema supports the current synchronous product:
stocks, watchlists, cached market/evidence data, single analysis runs, agent
outputs, citations, and token usage. It does not yet model a resumable,
branch-aware, multi-turn Debate or its background jobs.

Supabase Queues is a Postgres-native durable queue built on `pgmq`. A basic
queue creates active and archive tables inside the extension-owned `pgmq`
schema. Those transport tables are not the application's canonical Debate
record and their columns should not be duplicated or manually redesigned in
`public`.

Creating all anticipated tables during Phase 1 would make untested assumptions
about state transitions, idempotency, and RLS. Waiting until the Worker is
implemented to think about persistence would create the opposite problem: the
domain model and database model could diverge.

## Decision

Use separate, additive migrations owned by the phase that can test them:

| Phase | Database action |
| --- | --- |
| Phase 1 | Define and test database-independent domain contracts. Do not change deployed Supabase DDL. |
| Phase 2 | Extend the stock catalog and coverage metadata after catalog behaviour is characterized. |
| Phase 3 | Add `debate_sessions`, `debate_messages`, `debate_message_evidence`, `debate_interventions`, and `debate_jobs`; add grants, indexes, and two-user RLS tests in the same change. |
| Phase 4 | Persist only complete streamed messages through the Phase 3 repository; avoid schema changes unless streaming tests prove a missing invariant. |
| Phase 5 | Enable `pgmq`, create the durable `debate_jobs` queue, and add narrowly scoped server-side queue functions/permissions through a focused migration. |
| Phase 6 | Add Redis adapters without moving canonical Debate or job state out of Postgres. |

The application-owned `public.debate_jobs` table and the extension-owned queue
serve different purposes:

- `public.debate_jobs` is the queryable, user/session-linked job ledger and
  enforces idempotency and terminal state;
- `pgmq` stores delivery messages, visibility timing, retries, and archives;
- queue payloads contain only IDs, job type, schema version, idempotency key,
  and safe trace metadata;
- credentials, authorization headers, prompts, selected private text, and full
  evidence snapshots never enter a queue payload; and
- the mobile client never consumes the queue directly. It calls the API, while
  a server-side producer/Worker accesses Queue functions with server-only
  credentials.

The existing `analysis_runs` and `agent_outputs` relations remain readable as
legacy single-analysis history. New Debate tables are additive; they do not
rewrite old rows.

## Required gates before each migration

Every application-table migration must include:

1. a validated domain/state contract;
2. primary, foreign, uniqueness, and allowed-state constraints;
3. indexes for the API/Worker query paths;
4. explicit grants and RLS policies;
5. tests proving User A cannot access User B's records;
6. service-side access tests; and
7. an idempotent or clearly documented deployment procedure.

The Queue migration additionally requires redelivery, visibility-timeout,
archive/delete, duplicate-delivery, and Worker-restart tests. Redis is never the
only idempotency boundary.

## Consequences

- No Supabase table is changed during the first Phase 1 factor work.
- Field design happens early in domain models, but DDL is delayed until its
  persistence behaviour and RLS can be tested together.
- Queue transport can be replaced later without rewriting canonical Debate
  history.
- The project gains reviewable migration evidence for the portfolio instead of
  one speculative schema dump.
- Phase 3 and Phase 5 each require a database backup/verification checkpoint
  before applying their migration to the hosted project.

## References

- [Supabase Queues overview](https://supabase.com/docs/guides/queues)
- [Supabase Queues quickstart](https://supabase.com/docs/guides/queues/quickstart)
- [`pgmq` extension reference](https://supabase.com/docs/guides/queues/pgmq)
- [Supabase Row Level Security guide](https://supabase.com/docs/guides/database/postgres/row-level-security)

