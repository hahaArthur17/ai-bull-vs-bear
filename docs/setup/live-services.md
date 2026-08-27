# Live Services Setup

Last reviewed: 2026-08-27

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
GROQ_MODEL=llama-3.3-70b-versatile

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

Only after that gate, apply `20260827_v2_debate_persistence.sql` followed by
`20260827_v2_debate_persistence_rpc.sql`. Verify with two users that each can
read only their own Session, Message, citation, Intervention, and Job rows and
that direct authenticated writes are rejected. Then use the server-only secret
through backend tests/smoke tooling to verify atomic Session+Job creation,
Message+citations insertion, and expected-status updates. These migrations do
not enable the durable Queue.

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

## Verification checklist

- [x] `.env` exists locally and remains ignored by Git.
- [x] One real model provider is selected.
- [x] The selected model provider completes an analysis successfully.
- [x] The API response contains real token usage and no secret values.
- [x] The Supabase schema has been applied to the dedicated project.
- [x] Supabase contains public stocks, evidence documents, chunks, and vectors.
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
  provider; Groq was verified locally but is not required for the public demo.
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

The future Queue Worker will need a server-only Supabase secret on the backend.
Add it only during Queue Phase 5 after the new migrations, grants, RLS, and
Worker access tests pass. Redis configuration belongs to Phase 6 and must
remain optional with a tested fallback.

### Credential hygiene follow-up

The initially generated direct-database password was exposed during setup. Do
not use it. Confirm rotation in Supabase Database Settings before enabling any
direct Postgres connection. The current application uses project-scoped API
keys rather than that password.

## Rotation and incident response

If a credential is exposed in chat, logs, screenshots, or Git history, revoke
it immediately in the provider console and create a replacement. Removing a
secret from the current file is not enough once it has entered Git history.
