# Project Week 15 — Redis Coordination and Measured Cache Evidence

Date: 2026-08-29

Status: Phase 6 complete in code and local verification

## Goal

Finish the Redis phase without treating Redis as canonical persistence: wire
bounded admission coordination, prove API behaviour during an outage, and
record reproducible latency and repository-call evidence for a public hot read.

## Completed work

- Standard Debate factor snapshots reuse only immutable public context and
  never share generated text, Sessions, Messages, Jobs, or private questions.
- Per-user admission limits enforce one active Debate and three new admissions
  per default one-hour window.
- Queued creation requests use a hashed, owner-scoped idempotency lock before
  factor work; deterministic IDs and PostgreSQL constraints remain canonical.
- Simulated Redis timeouts across reads, writes, locks, counters, releases, and
  probes preserve correct stock-search and queued-Debate API behaviour.
- `GET /health/cache` exposes safe cache mode, reachability, and degraded
  operation counts without URLs, keys, credentials, or exception messages.
- `scripts/benchmark_stock_search_cache.py` provides a network-free,
  repeatable stock-search latency and repository-call benchmark.

## Benchmark method

The benchmark runs `GET /stocks?q=aapl&limit=20` through FastAPI TestClient on
macOS 26.5.2 arm64 with Python 3.13.4. Each profile compares:

- 100 requests with caching disabled (`BYPASS`);
- 100 requests with caching enabled (one `MISS`, then 99 `HIT`s); and
- the number of `DemoStore.list_stocks` calls made by each scenario.

One `/health` request warms the in-process HTTP test transport before timing.
The zero-delay profile measures local application work. The second profile adds
an explicit 5 ms delay to each repository call so the cache boundary can be
measured under controlled persistence latency. The cache itself is the local
adapter, which avoids introducing a real network dependency into the benchmark.

Reproduction commands:

```text
PYTHONPATH=backend backend/.venv/bin/python \
  scripts/benchmark_stock_search_cache.py \
  --iterations 100 --repository-delay-ms 0

PYTHONPATH=backend backend/.venv/bin/python \
  scripts/benchmark_stock_search_cache.py \
  --iterations 100 --repository-delay-ms 5
```

## Recorded results

| Controlled repository delay | Uncached median / p95 | Cold MISS | HIT median / p95 | Median speedup | Repository calls, uncached → cached | Calls avoided |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 ms | 3.787 / 4.023 ms | 3.999 ms | 0.692 / 0.781 ms | 5.47x | 100 → 1 | 99 (99%) |
| 5 ms | 10.352 / 11.002 ms | 10.864 ms | 0.711 / 0.796 ms | 14.56x | 100 → 1 | 99 (99%) |

Both cached runs returned one `MISS`, 99 `HIT`s, no `DEGRADED` result, and the
same validated AAPL payload on every iteration. The evidence demonstrates the
intended repeated-read effect: the first request still pays the collection and
serialization cost, while subsequent requests avoid 99 repository calls.

## Verification

```text
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
305 passed, 1 existing Starlette/httpx deprecation warning
```

The full suite also proves cache status accounting, privacy-safe keys, factor
provider-call avoidance, one canonical Job for duplicate submissions, and
correct local fallback when Redis operations time out.

## Limits of this evidence

- These are local, in-process measurements, not hosted Supabase or Redis
  round-trip measurements and not a production latency SLA.
- The controlled 5 ms delay is an explicit test input, not a claim about a
  provider's real response time.
- The benchmark does not model concurrent clients, multi-process contention,
  internet variability, or hosted free-tier cold starts.
- A future deployment pass may add live Redis/Supabase observations, but it
  must keep these local numbers separate from hosted results.

## Recommended next tasks

1. Run one quota-controlled live Groq streaming smoke test.
2. Begin the bounded Explanation Agent slice without coupling it to Debate
   state transitions.
3. Continue device/accessibility checks for the default-off V2 experience.

## Related documents

- [`current-status.md`](../current-status.md)
- [`portfolio-implementation-plan.md`](../portfolio-implementation-plan.md)
- [`backend/README.md`](../../../backend/README.md)
- [`api-contract.md`](../../api/api-contract.md)

## Follow-up — hosted migration preflight

A 2026-08-29 read-only check matched the signed-in `AI Bull vs Bear` Dashboard
project to the configured API project and found it healthy. The existing
two-user Watchlist verifier again passed owner access, hidden cross-user reads,
rejected cross-user writes, and persistence through a new connection.

PostgREST metadata confirmed that the five catalog coverage columns, ranked
search RPC, five Debate tables, two persistence RPCs, and seven Queue RPCs are
not deployed. The local machine has no Supabase CLI, `psql`, database URL, or
Management API token, so the already authenticated Dashboard SQL Editor is the
available controlled migration surface. No SQL was run in this preflight.

`scripts/verify_supabase_migration_preflight.py` now reproduces this inspection
without printing the project URL, server key, remote response body, or table
content. Its output lists the three catalog, two Debate persistence, and one
Queue migration in order. The next action is the documented read-only database
size query; migration execution must not begin if the database exceeds the
400 MB capacity gate.

## Follow-up — hosted Catalog deployment

On 2026-08-29 the capacity query reported 23,727,251 bytes (23 MB), below the
400 MB stop threshold. The coverage and search migrations completed in filename
order. The 1.14 MB seed exceeded the SQL Editor's single-query limit, so its
existing 16 bounded, idempotent INSERT statements were executed unchanged in
six smaller transactions. All six succeeded and produced 7,695 active rows
while preserving the four curated `debate_ready` rows.

The deployed `stocks` relation measured 1,294,336 bytes for the table and
4,513,792 bytes for indexes, or 5,849,088 bytes total (about 5.7 MiB), below the
15 MiB acceptance budget. The whole database measured 30,157,971 bytes after
deployment. Anonymous PostgREST RPC search returned `MSFT` / `MICROSOFT CORP`
for `microsoft` with status 200.

The reusable migration preflight now reports Catalog columns and the ranked
search RPC as deployed, with only the two Debate persistence migrations and the
Queue migration remaining. The two-user Watchlist verifier again passed owner
read, hidden cross-user reads, rejected cross-user writes, and persistence
through a new connection. Phase 2 is therefore complete; the next controlled
slice is the Debate persistence/RLS/service-role gate.

## Follow-up — hosted Debate persistence deployment

On 2026-08-29 the two Debate persistence migrations completed in filename
order; the Queue migration was deliberately not run. PostgREST metadata then
reported all five canonical tables plus `create_debate_session_with_job` and
`append_debate_message`, with only the Queue migration remaining.

The preflight verifier was corrected to use the same `append_debate_message`
path as the migration, runtime repository, and SQL contract tests. The new
`scripts/verify_supabase_debate_persistence.py` performs a disposable hosted
smoke test with both configured RLS users and the server-only key. It passed:

- both users saw their own Session, Message, citation, Intervention, and Job;
- both users saw no rows belonging to the other user;
- authenticated writes to all five tables and calls to both transaction RPCs
  were rejected;
- the server-only repository atomically and idempotently created Session+Job,
  applied expected-status updates, inserted Message+citations, and wrote an
  Intervention; and
- deleting both temporary Sessions removed the verification data.

The complete backend suite now passes with 308 tests and the same existing
Starlette/httpx deprecation warning. Phase 3 is complete on hosted Supabase;
production V2 flags remain off because Queue/Worker/restart verification is the
next controlled slice.

## Follow-up — hosted Queue deployment

On 2026-08-29 `20260828_v2_debate_queue.sql` completed in the controlled SQL
Editor. PostgREST metadata exposed all seven service-only Queue RPCs and the
migration preflight returned no required files.

The new `scripts/verify_supabase_debate_queue.py` ran a disposable,
deterministic hosted lifecycle through fresh service clients. It proved:

- idempotent atomic admission for Round 1 and Round 2;
- bounded Workers completed the canonical 13-message two-round transcript;
- a forced visibility retry recovered a running Job with `read_count=2` and
  `attempt_count=2` through a new client;
- an exhausted Job reached its safe terminal state;
- authenticated users were rejected by all seven Queue RPCs; and
- cascading Session cleanup removed canonical data, after which only the exact
  Queue message IDs printed by the verifier were removed from active/archive
  transport tables.

Final SQL checks reported zero active Queue messages, archived Queue messages,
Sessions, Messages, Interventions, and Jobs. The full backend suite passes with
310 tests and the same existing Starlette/httpx deprecation warning. Phase 5 is
complete in its controlled hosted scope. Production V2 and Queue flags remain
default-off pending a deliberate rollout and quota-controlled live Groq smoke
test.
