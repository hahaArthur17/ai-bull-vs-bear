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

SEC_USER_AGENT=AI Bull vs Bear contact@example.com

ALPHA_VANTAGE_API_KEY=
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
5. Keep the service-role key server-side only. It must never be bundled into the
   Expo application.
6. Verify row-level security with two separate test users before relying on the
   project for persisted user data.

`SUPABASE_SECRET_KEY` is used only by the backend ingestion script. The mobile
app needs only the publishable/anon key.

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

## Alpha Vantage daily prices

Official documentation:

- <https://www.alphavantage.co/documentation/#daily>
- <https://www.alphavantage.co/support/>

`TIME_SERIES_DAILY` with `outputsize=compact` returns the latest 100 daily
OHLCV points. The free service currently permits 25 requests per day, so the
application uses a batch cache: one four-ticker refresh consumes four calls,
and normal API/mobile reads use Supabase instead of calling Alpha Vantage.

After placing the key in `ALPHA_VANTAGE_API_KEY`, run from the repository root:

```shell
PYTHONPATH=backend python scripts/ingest_live_prices.py
```

Temporary provider failure leaves the previous cache untouched. Empty,
unavailable, or older-than-configured caches are identified in the API; an
unavailable cache falls back to deterministic demo prices.

## Verification checklist

- [x] `.env` exists locally and remains ignored by Git.
- [x] One real model provider is selected.
- [x] The selected model provider completes an analysis successfully.
- [x] The API response contains real token usage and no secret values.
- [x] The Supabase schema has been applied to the dedicated project.
- [x] Supabase contains public stocks, evidence documents, chunks, and vectors.
- [x] SEC parsing, throttling, retry, and metadata fallback pass mocked tests.
- [x] Alpha Vantage parsing, retries, Supabase upsert, and read fallback pass
  mocked tests.
- [ ] Authentication works for a test user.
- [ ] Watchlist and analysis history survive a backend restart.
- [ ] Row-level security prevents one user from reading another user's data.
- [ ] Refresh live evidence with a server secret and compliant SEC User-Agent.
- [ ] Populate the price cache with a server secret and Alpha Vantage key.

## Current live configuration

Last verified: 2026-08-15

- Groq is the selected local provider, and a real structured analysis completed
  successfully with provider token usage.
- The dedicated Supabase project is running in the Asia-Pacific region.
- Supabase authentication, bearer-token forwarding, persistent watchlists, and
  persistent analysis history are implemented. The local backend selects the
  Supabase auth and persistence modes, but two-user live RLS verification is
  still required.
- A read-only live check returned AAPL, GOOG, NVDA, and TSLA plus six evidence
  documents (two news and four filing records), six chunks, and six populated
  vectors.
- The current database rows predate the selected-section importer and have no
  `content_status`; rerun ingestion after configuring a server secret and a
  compliant SEC User-Agent to replace the filing metadata with real excerpts.
- The `stock_prices` table is currently empty. Price ingestion and mobile
  provenance display are implemented, but the local environment has neither a
  server secret nor an Alpha Vantage key, so live price refresh is unverified.
- The initially generated database password was exposed during setup and must
  be rotated in the Supabase Database Settings page before direct Postgres
  connections are used.

## Rotation and incident response

If a credential is exposed in chat, logs, screenshots, or Git history, revoke
it immediately in the provider console and create a replacement. Removing a
secret from the current file is not enough once it has entered Git history.
