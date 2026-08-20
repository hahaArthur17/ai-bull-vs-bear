# Live Services Setup

This document records the non-secret configuration needed to move AI Bull vs
Bear from deterministic demo mode to real services.

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

`SUPABASE_SECRET_KEY` is used only by the backend ingestion script. The mobile
app needs only the publishable/anon key.

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
- [ ] Watchlist and analysis history survive a backend restart.
- [x] Row-level security prevents one user from reading or writing another
  user's watchlist data.
- [x] Refresh live evidence with a server secret and compliant SEC User-Agent.
- [ ] Populate the price cache with a server secret and Alpha Vantage key.
- [x] Populate structured SEC XBRL facts with a server secret and compliant
  SEC User-Agent.

## Current live configuration

Last verified: 2026-08-15

- Groq is the selected local provider, and a real structured analysis completed
  successfully with provider token usage.
- The dedicated Supabase project is running in the Asia-Pacific region.
- Supabase authentication, bearer-token forwarding, persistent watchlists, and
  persistent analysis history are implemented. Two disposable users now pass
  owner read/write, hidden cross-user reads, rejected cross-user writes, and
  database-reconnect persistence checks.
- A read-only live check returned AAPL, GOOG, NVDA, and TSLA plus six evidence
  documents (two news and four filing records), six chunks, and six populated
  vectors.
- The 2026-08-15 embedding-profile migration is live. All six existing vectors
  are registered as `local-hash-v1` with 1,536 dimensions, and anonymous vector
  RPC retrieval still succeeds. This profile is a deterministic word-hash
  integration baseline, not a learned semantic model.
- A dedicated server-only current-format secret key is configured locally.
  Service-role grants and request headers support that key without broadening
  anon/authenticated privileges.
- Live ingestion now holds 20 evidence documents, 107 contextual chunks, and
  611 typed financial facts. Filing records include selected narrative sections
  when SEC source HTML is available.
- The `stock_prices` table is currently empty. Price ingestion and mobile
  provenance display are implemented, but Alpha Vantage terms acceptance and
  key issuance are still pending, so live price refresh is unverified.
- The initially generated database password was exposed during setup and must
  be rotated in the Supabase Database Settings page before direct Postgres
  connections are used.

## Rotation and incident response

If a credential is exposed in chat, logs, screenshots, or Git history, revoke
it immediately in the provider console and create a replacement. Removing a
secret from the current file is not enough once it has entered Git history.
