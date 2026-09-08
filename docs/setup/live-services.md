# Live Services Setup

Last reviewed: 2026-09-08

This document records the non-secret configuration needed to move AI Bull vs
Bear from deterministic demo mode to real services.

It is a setup guide, not the active backlog or current-state source of truth.
Use [`current-status.md`](../planning/current-status.md) and the
[`portfolio implementation plan`](../planning/portfolio-implementation-plan.md)
for those purposes.

Never commit `.env`, API keys, database passwords, service-role keys, access
tokens, or screenshots that display credentials.

## Local environment file

Create `.env` at the repository root from `.env.example`. The application reads
these variables when the backend starts.

```dotenv
ENVIRONMENT=development
AUTH_MODE=supabase
PERSISTENCE_MODE=supabase
ANALYSIS_PROVIDER=groq
CORS_ORIGINS=http://localhost:8081,http://localhost:19006

SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SECRET_KEY=
SUPABASE_RLS_USER_A_EMAIL=
SUPABASE_RLS_USER_A_PASSWORD=
SUPABASE_RLS_USER_B_EMAIL=
SUPABASE_RLS_USER_B_PASSWORD=

SEC_USER_AGENT=AI Bull vs Bear contact@example.com

ALPHA_VANTAGE_API_KEY=
FINNHUB_API_KEY=
PRICE_TICKERS=AAPL
PRICE_MAX_CALLS_PER_RUN=1
PRICE_STALE_AFTER_DAYS=5

GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
DEBATE_STREAMING_PROVIDER=deterministic
DEBATE_GROQ_MODEL=openai/gpt-oss-20b
DEBATE_PROVIDER_TIMEOUT_SECONDS=45
EXPLANATION_PROVIDER=deterministic
EXPLANATION_GROQ_MODEL=openai/gpt-oss-20b
EXPLANATION_PROVIDER_TIMEOUT_SECONDS=20
EXPLANATION_MAX_COMPLETION_TOKENS=320

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
```

Only one model provider needs to be active. Keep unused provider keys empty.

## Groq

Console: <https://console.groq.com/keys>

1. Create a key for the current Groq project with a descriptive name such as
   `ai-bull-vs-bear-local`.
2. Copy it once and place it in `GROQ_API_KEY` in the local `.env` file.
3. Set `ANALYSIS_PROVIDER=groq`.
4. Restart the backend and run one analysis request.
5. Confirm that `token_usage.model_name` contains the configured Groq model.

The former default `llama-3.3-70b-versatile` was retired for Free and
Developer accounts on 2026-08-16. `openai/gpt-oss-20b` is the current bounded
default. The live Debate path is a separate opt-in: change
`DEBATE_STREAMING_PROVIDER` from `deterministic` to `groq` only for an explicit
local smoke test or after the asynchronous Worker path is deployed. This avoids
spending six model requests merely by enabling the V2 HTTP preview.

Run the live Round 1 verifier only with explicit quota confirmation:

```shell
DEBATE_STREAMING_PROVIDER=groq PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_groq_debate_streaming.py \
  --confirm-live-quota
```

The command makes at most six non-retried Groq Turn requests, caps each at 220
completion tokens, limits the provider transcript to 300 characters per prior
message, persists only in memory, and never prints generated text or
credentials. Recorded 2026-08-29 result: `openai/gpt-oss-20b` completed all six
Turns plus the local deterministic Judge. The run persisted seven canonical
messages, emitted 697 ordered deltas, linked 11 valid citations, resumed from a
stream cursor, reloaded canonical state, and recorded 6,041 prompt plus 939
completion tokens (6,980 total). Production configuration was not changed.

Term Explanation is a separate provider choice. Keep
`EXPLANATION_PROVIDER=deterministic` for normal development, tests, and the
deployed baseline. To verify the real Explanation transport locally, set it to
`groq` and run the following command only after accepting one provider request:

```shell
EXPLANATION_PROVIDER=groq PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_groq_explanation.py \
  --confirm-live-quota
```

The verifier sends one synthetic complete message and linked synthetic evidence,
caps completion at 160 tokens, prints no generated text or credentials, and
does not write a Session, Job, Message, or production setting. A successful
local run is evidence for credential and provider compatibility, not approval to
enable Groq in production.

Recorded local result on 2026-08-29: `openai/gpt-oss-20b` completed the single
request with 625 bounded output characters and one linked evidence citation;
all request, output, evidence, and term checks passed. No generated text or
credentials were printed, and production configuration was unchanged.

## Gemini

Console: <https://aistudio.google.com/api-keys>

Gemini is an alternative model provider. Create and configure a Gemini key only
when it will be used; the app does not require both Groq and Gemini at once.

1. Create or select a Google Cloud project dedicated to this application.
2. Create an API key and restrict it to the relevant Gemini/Generative Language
   API where supported.
3. Place the value in `GEMINI_API_KEY` and set
   `ANALYSIS_PROVIDER=gemini`.
4. Restart the backend and verify a real analysis response.

## Supabase

Dashboard: <https://supabase.com/dashboard>

1. Create a dedicated project named `AI Bull vs Bear`; do not reuse an
   unrelated production project.
2. Open SQL Editor and run `backend/supabase/schema.sql`.
3. Enable the required sign-in method under Authentication.
4. Copy the project URL and publishable/anon key into `SUPABASE_URL` and
   `SUPABASE_ANON_KEY`.
5. Create a dedicated current-format secret key (`sb_secret_...`) for backend
   jobs and keep it server-side only. It must never be bundled into the Expo
   application. Legacy JWT `service_role` keys remain supported during
   migration.
6. Verify row-level security with two separate test users before relying on the
   project for persisted user data.

Before applying the Phase 2 catalog migrations, run this in SQL Editor:

```shell
PYTHONPATH=backend backend/.venv/bin/python \
  scripts/verify_supabase_migration_preflight.py
```

This read-only preflight inspects PostgREST metadata using the server-only key,
reports which catalog, Debate, and Queue surfaces are already deployed, and
prints the required migration filenames in canonical order. It never executes
SQL or prints the project URL, key, remote error body, or table contents. A
missing catalog still requires the following database-size query before any
catalog migration is run.

```sql
select
  pg_size_pretty(pg_database_size(current_database())) as database_size,
  pg_database_size(current_database()) as database_bytes;
```

Do not apply the full catalog when `database_bytes` is above 400,000,000
(400 MB). This project keeps 100 MB of the Free Plan's 500 MB database quota
as headroom for evidence, vectors, Debate history, Queue metadata, and normal
Postgres growth.

Apply `20260827_stock_catalog_coverage.sql`,
`20260827_stock_catalog_search.sql`, and
`20260827_stock_catalog_seed.sql` in filename order. Then record the actual
catalog footprint:

```sql
select
  pg_size_pretty(pg_relation_size('public.stocks')) as table_only,
  pg_size_pretty(pg_indexes_size('public.stocks')) as indexes,
  pg_size_pretty(pg_total_relation_size('public.stocks')) as total_with_indexes,
  pg_size_pretty(pg_database_size(current_database())) as database_total;
```

The accepted catalog budget is 15 MiB including indexes. Stop and investigate
if the measured `total_with_indexes` exceeds it. Before marking Phase 2
deployed, confirm an anon/public catalog search succeeds and repeat the existing
two-user test proving that each user can change only their own Watchlist.

Recorded 2026-08-29 deployment result: the database passed the preflight at
23,727,251 bytes. The three Catalog migrations produced 7,695 active rows and
preserved four `debate_ready` rows. `stocks` measured 1,294,336 table bytes plus
4,513,792 index bytes, 5,849,088 bytes total; the full database then measured
30,157,971 bytes. Anonymous ranked search returned MSFT for `microsoft`, and the
two-user Watchlist RLS/reconnect verifier passed all four checks. The Catalog
gate is complete. Debate persistence and Queue subsequently passed their own
gates, so the current preflight reports no required migrations.

Only after that gate, apply `20260827_v2_debate_persistence.sql` followed by
`20260827_v2_debate_persistence_rpc.sql`. Verify with two users that each can
read only their own Session, Message, citation, Intervention, and Job rows and
that direct authenticated writes are rejected. Then use the server-only secret
through backend tests/smoke tooling to verify atomic Session+Job creation,
Message+citations insertion, and expected-status updates. These migrations do
not enable the durable Queue.

Recorded 2026-08-29 deployment result: both migrations completed in order and
PostgREST exposed all five tables plus both runtime RPCs. Run the reusable
hosted verifier with the backend virtual environment:

```shell
PYTHONPATH=backend backend/.venv/bin/python \
  scripts/verify_supabase_debate_persistence.py
```

It creates one disposable fixture for each configured RLS user, proves own-row
visibility and cross-user isolation on all five tables, rejects authenticated
table/RPC writes, exercises atomic/idempotent service-only writes and status
updates, and deletes both Sessions with their cascading child rows. The
recorded run passed every check.

Apply `20260828_v2_debate_queue.sql` only after Debate persistence is present.
Then run the hosted Queue verifier with the backend virtual environment:

```shell
PYTHONPATH=backend backend/.venv/bin/python \
  scripts/verify_supabase_debate_queue.py
```

The verifier uses disposable canonical data and fresh service clients to prove
idempotent Round 1/2 admission, the complete 13-message transcript,
claim/archive, delayed redelivery, recovery after a running Job restart,
attempt exhaustion, authenticated-user RPC rejection, and cascading Session
cleanup. It prints the exact Queue message IDs created by that run. Remove only
those IDs from the extension-owned transport tables in SQL Editor, never the
whole Queue:

```sql
delete from pgmq.q_debate_jobs where msg_id in (<verifier_message_ids>);
delete from pgmq.a_debate_jobs where msg_id in (<verifier_message_ids>);
```

Recorded 2026-08-29 deployment result: all seven Queue RPCs were exposed to the
service boundary. Both rounds completed idempotently, the fresh-client restart
case recovered a running Job with `read_count=2` and `attempt_count=2`, the
exhaustion case reached its safe terminal state, and authenticated calls to
all seven RPCs were rejected. Exact verifier artifacts were deleted; final
active Queue, archive Queue, Session, Message, Intervention, and Job counts
were all zero. The migration preflight then returned an empty required list.

`SUPABASE_SECRET_KEY` is currently used by backend ingestion; the V2 Debate
repository will also use it after its runtime is enabled. It remains
server-side. The mobile app needs only the publishable/anon key.

Current `sb_secret_...` keys are sent only in Supabase's `apikey` header. They
are opaque API keys, not JWTs, so placing one in `Authorization: Bearer` causes
Data API requests to fail. The backend request helper adds the Bearer header
only for a legacy JWT key.

Web-dashboard account passwords must not be stored in the project environment.
For repeatable RLS verification, use only two disposable, non-production Auth
users and store their credentials in the four `SUPABASE_RLS_*` variables in the
ignored local `.env`. Then run:

```shell
PYTHONPATH=backend python scripts/verify_supabase_rls.py
```

The script proves owner reads/writes, hidden cross-user reads, rejected
cross-user writes, and persistence after opening a new database connection. It
removes the temporary watchlist rows in a `finally` block. It never prints
passwords or access tokens.

## SEC EDGAR evidence

Official guidance:

- <https://www.sec.gov/about/developer-resources>
- <https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data>

SEC asks automated clients to declare a User-Agent with identifying contact
information and currently limits access to 10 requests per second. Set
`SEC_USER_AGENT` to the project name plus a monitored email address; do not
commit a personal address if it should remain private.

From the repository root, with the backend virtual environment active, run:

```shell
PYTHONPATH=backend python scripts/ingest_live_evidence.py
```

The script imports the configured RSS source and recent supported-ticker 10-K
and 10-Q filings. Filing HTML is reduced to Risk Factors and Management's
Discussion and Analysis excerpts before it is chunked in Supabase. Requests
are spaced below the SEC limit and retry temporary 429/5xx failures. A filing
that remains unavailable is retained as metadata-only evidence so one outage
does not discard the rest of the batch.

The same run also calls the official SEC `companyfacts` endpoint and upserts a
bounded set of common revenue, earnings, balance-sheet, cash-flow, share, and
EPS concepts into `financial_facts`. Each value keeps its taxonomy, unit,
period, filing date, accession, and source URL. Numerical comparisons must use
these typed facts rather than asking a text embedding to infer table structure.

## Alpha Vantage daily prices

Official documentation:

- <https://www.alphavantage.co/documentation/#daily>
- <https://www.alphavantage.co/support/>

`TIME_SERIES_DAILY` with `outputsize=compact` returns the latest 100 daily
OHLCV points. The free service currently permits 25 requests per day, so the
application uses a batch cache: the default AAPL-only refresh makes one call
with no retries, and normal API/mobile reads use Supabase instead of calling
Alpha Vantage. Run the command no more than once per trading day.

After placing the key in `ALPHA_VANTAGE_API_KEY`, run from the repository root:

```shell
PYTHONPATH=backend python scripts/ingest_live_prices.py
```

Temporary provider failure leaves the previous cache untouched. Empty,
unavailable, or older-than-configured caches are identified in the API; the
mobile UI withholds synthetic fallback prices, charts, and indicators instead
of presenting them as market data.

`PRICE_TICKERS` can select one to three symbols and
`PRICE_MAX_CALLS_PER_RUN` can lower the hard per-invocation cap. The configured
cap cannot be raised above three.

## Optional Apify and Finnhub credentials

The ignored local `.env` may also define `APIFY_USER_ID`, `APIFY_API_TOKEN`,
and `FINNHUB_API_KEY`. These values are server-side only and must not use the
`EXPO_PUBLIC_` prefix.

Finnhub provides the current quote returned by `GET /stocks/{ticker}/quote`.
The backend caches it for 60 seconds and labels it as a quote, not a closing
price. Finnhub can also populate the daily-price cache when the configured
account has daily-candle permission; otherwise Alpha Vantage is the supported
free source for the curve. Apify is an automation platform rather than a single
financial dataset, so an Actor or saved task and its expected output schema must
be selected before an ingestion adapter can be implemented.

## Controlled Expo Go Live Acceptance profile

Status: planned, not executed by the 2026-09-08 planning update. The canonical
scope and acceptance gates are WP8L in
[`phase-8-design-remediation.md`](../planning/phase-8-design-remediation.md).

This profile is deliberately separate from `review_fixture`. A safe
presence-only audit confirms that the ignored local `.env` has Supabase, Groq,
Alpha Vantage, Finnhub, and SEC settings, but the V2/Queue/live-provider/Expo V2
flags are unset and therefore use safe disabled/deterministic defaults. Never
record or print the credential values.

### 1. Confirm provider truth before any write or model call

- Recheck the active Groq model through the Models API and current provider
  limits. A model ID that worked in an earlier report is not permanent evidence.
- Treat Finnhub `/quote` as a latest provider quote with its own timestamp. It
  is not a historical completed close.
- Treat the newest Alpha Vantage daily row as the latest completed OHLCV close
  for chart/indicator calculations. `TIME_SERIES_DAILY` is a daily-history
  source, not the app's real-time quote channel.
- Confirm the intended request budget before each live test. The existing Round
  1 verifier makes at most six non-retried Bull/Bear requests; Judge and
  Explanation have separate provider contracts and budgets.

### 2. Refresh real AAPL inputs, one bounded source at a time

These commands write provider data into the configured Supabase project. Run
them only after explicit authorization and no more frequently than their source
budgets require:

```shell
PYTHONPATH=backend backend/.venv/bin/python scripts/ingest_live_prices.py
PYTHONPATH=backend backend/.venv/bin/python scripts/ingest_live_evidence.py
PYTHONPATH=backend backend/.venv/bin/python scripts/ingest_macro_context.py
PYTHONPATH=backend backend/.venv/bin/python scripts/ingest_aapl_weekly_history.py
```

The weekly command is conditional on the cache being due. After each write,
read back the source, observation/publication time, retrieval time, record count,
stale state, and data mode. Stop before model use if the daily cache failed to
advance when expected, fewer than 50 valid closes remain, or simulated/fallback
provenance appears.

### 3. Run the quota-bounded provider verifier

After revalidating the model and accepting six provider requests:

```shell
DEBATE_STREAMING_PROVIDER=groq PYTHONPATH=backend \
  backend/.venv/bin/python scripts/verify_groq_debate_streaming.py \
  --confirm-live-quota
```

Require ordered deltas, six complete Bull/Bear Turns, valid citation IDs,
nonzero token accounting, reconnect, and cleanup. The present verifier uses a
deterministic local Judge; it is not proof that every visible agent is live.

### 4. Start one controlled standard-mode session

Use a dedicated non-production Supabase user. Keep API, Worker, and event broker
in one process because live deltas are currently process-local. Do not use
`--reload` during a quota-bearing Session.

```shell
cd backend
ENVIRONMENT=development APP_DATA_MODE=standard \
DEBATE_WORKFLOW_V2=true DEBATE_QUEUE_ENABLED=true \
DEBATE_STREAMING_PROVIDER=groq \
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For the iOS Simulator:

```shell
cd apps/mobile
EXPO_PUBLIC_AUTH_MODE=supabase \
EXPO_PUBLIC_DEBATE_V2_ENABLED=true \
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 \
npx expo start --localhost --clear
```

A physical device uses the workstation LAN address instead of loopback. Before
starting Debate, read `/health`, `/stocks/AAPL/quote`,
`/stocks/AAPL/bundle`, `/stocks/AAPL/evidence`, and the current Debate list.
Confirm standard mode, fresh/dated provenance, no fixture IDs, no unfinished
Session conflict, and one declared model-call budget.

### 5. Know what still blocks final Live Acceptance

- Bull/Bear can stream through Groq today; Interim/Final Judge remain
  deterministic and non-streaming until an asynchronous Judge contract is
  implemented.
- Provider chunks do not guarantee one word or character per event. A client
  reveal scheduler must buffer deltas and release words/graphemes at a controlled
  pace without letting canonical completion jump to full text.
- Current terminal Cancel clears incomplete drafts. The accepted `Stop here`
  behavior instead freezes the visible prefix, discards undisplayed text,
  prevents every later agent, persists an explicitly incomplete prefix, and
  opens a user-interjection decision before any continuation.
- A separate Worker or multiple API instances cannot deliver reliable live
  deltas/interruption through the current process-local broker. Add a shared or
  durable delta/checkpoint layer before changing topology.

Do not enable hosted or public V2/Queue/Groq flags until the local Expo pass,
same-SHA staging smoke, rollback, quota, and provenance gates are recorded.

## Verification checklist

- [x] `.env` exists locally and remains ignored by Git.
- [x] One real model provider is selected.
- [x] The selected model provider completes an analysis successfully.
- [x] One quota-controlled local Groq Round 1 completes ordered live Turn
  streaming, canonical persistence, citations, token accounting, and reconnect.
- [x] The API response contains real token usage and no secret values.
- [x] The Supabase schema has been applied to the dedicated project.
- [x] Supabase contains public stocks, evidence documents, chunks, and vectors.
- [x] Hosted Catalog has 7,695 active rows, fits the 15 MiB relation budget, and
  passes anonymous ranked search.
- [x] Hosted Debate persistence exposes five owner-read tables and two
  service-only RPCs; the disposable two-user verifier passes and cleans up.
- [x] Hosted Queue exposes seven service-only RPCs; disposable two-round,
  retry, restart, exhaustion, authorization, and cleanup checks pass.
- [x] Embedding profiles and the structured `financial_facts` table are applied.
- [x] SEC parsing, throttling, retry, and metadata fallback pass mocked tests.
- [x] Alpha Vantage parsing, retries, Supabase upsert, and read fallback pass
  mocked tests.
- [x] Authentication works for two disposable test users.
- [x] Watchlist and analysis history survive a backend restart.
- [x] Row-level security prevents one user from reading or writing another
  user's watchlist data.
- [x] Refresh live evidence with a server secret and compliant SEC User-Agent.
- [x] Populate the AAPL price cache with a server secret and Alpha Vantage key.
- [x] Populate structured SEC XBRL facts with a server secret and compliant
  SEC User-Agent.

## Last verified live-service baseline

The detailed data/deployment evidence is retained in the
[`Week 6 report`](../planning/reports/project-week-06.md). As of the latest
checks:

- Production uses Supabase Auth/persistence and the deterministic analysis
  provider. A six-request local Groq Round 1 passed streaming, persistence,
  citation, token, and reconnect checks; Groq remains unnecessary for the
  public demo.
- Two-user tests proved owner access, cross-user RLS isolation, and persistence
  across a new backend/database connection.
- AAPL has verified daily and separately labelled weekly price caches. Normal
  screen/API reads do not call the market-data provider.
- Apple Newsroom/SEC evidence, contextual chunks, vectors, and structured SEC
  facts are stored with source metadata.
- Seven FRED/EIA series are cached and exposed as dated, non-causal market
  background.
- Public frontend and API health were rechecked on 2026-08-27; the API reported
  `environment=production` and `provider=demo`.
- Hosted Catalog deployment was verified on 2026-08-29: 7,695 active identities,
  5,849,088 bytes including indexes, anonymous search success, and unchanged
  two-user Watchlist RLS isolation.
- Hosted Debate persistence was verified on 2026-08-29: five-table owner
  isolation, rejected authenticated writes/RPCs, service-only atomic and
  idempotent writes, expected-status updates, and complete fixture cleanup.
- Hosted Queue was verified on 2026-08-29: both rounds produced 13 canonical
  messages, idempotent admission and fresh-client retry/restart passed,
  exhausted work failed safely, authenticated RPC access was rejected, and
  exact canonical/transport artifacts were removed.

The implemented, default-off Queue Worker needs the existing server-only
Supabase secret on the backend. Its migration and deterministic hosted
lifecycle checks are complete; keep the Queue flag disabled until a deliberate
production rollout has an explicit deployment smoke-test and rollback plan.
The first Phase 6 Redis slice is implemented but remains optional. Keep
`REDIS_ENABLED=false` unless a deliberate test supplies a `redis://` or
`rediss://` `REDIS_URL`. Stock search and the public stock bundle fail open to a
bounded local fallback; Redis is not canonical persistence or Queue transport.
The standard `question=null` Debate may reuse only its public normalized factor
snapshot for six hours; custom questions bypass this cache. Rate limits and
the one-active-Debate rule run through Redis when enabled and the bounded local
fallback otherwise. Their safe defaults are three admissions per 3,600 seconds
and a 1,200-second active-key TTL; canonical non-terminal Sessions remain the
authority after the TTL. Owner-scoped Debate idempotency locking is implemented
with deterministic database uniqueness as the degraded fallback.

### Credential hygiene follow-up

The initially generated direct-database password was exposed during setup. Do
not use it. Confirm rotation in Supabase Database Settings before enabling any
direct Postgres connection. The current application uses project-scoped API
keys rather than that password.

## Rotation and incident response

If a credential is exposed in chat, logs, screenshots, or Git history, revoke
it immediately in the provider console and create a replacement. Removing a
secret from the current file is not enough once it has entered Git history.


### 2026-09-09 snapshot engineering checkpoint

The backend snapshot now records separate quote/close observations and capture
time. Finnhub retrieval time survives cache hits. Live Turn admission uses a
15-minute quote age limit during the current regular session and 72 hours
otherwise; these are application limits, not provider guarantees. Daily rows
must be ordered, unique, positive, fresh, and at least 50 in number, with a
conservative New York 16:15/weekend cutoff. Holidays and early closes still
require an authoritative calendar. Evidence/filing/macro admission and the
full live preflight are pending. No data refresh, model call, or hosted flag
change was performed for this checkpoint.
