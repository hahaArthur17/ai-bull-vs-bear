# Backend

Last reviewed: 2026-10-17.

FastAPI serves stock research, owner-scoped Watchlist/History, the legacy
single-response analysis, and a separately enabled two-round Debate V2. Core
implementation and local automated checks are complete; physical-device and
existing-Render release acceptance remain open. See the
[current status](../docs/planning/current-status.md) for the release boundary.

## Local setup and deterministic review

From the repository root on a fresh clone:

```sh
cp .env.example .env
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
ENVIRONMENT=development APP_DATA_MODE=review_fixture \
  .venv/bin/python -m uvicorn app.main:app \
  --reload --host 0.0.0.0 --port 8000
```

Keep an existing ignored `.env` rather than overwriting credentials. Settings
load that root file regardless of the working directory; shell variables take
precedence. CI uses Python 3.12 and the Docker runtime uses Python 3.13.

Open [health](http://localhost:8000/health) or
[interactive OpenAPI](http://localhost:8000/docs). `/health` reports
status/environment, data and legacy-provider modes, the V2 flag, and optional
`build_sha`. Set `APP_BUILD_SHA` to the launched commit when recording acceptance.

`review_fixture` is an explicit local-only profile. It forces demo auth and
in-memory persistence, deterministic Turn/Judge/Explanation providers, V2 on,
Queue off, and Redis off, even if the root `.env` contains live credentials.
It makes no Supabase, market-data, model, or Redis request. AAPL is fresh, GOOG
stale, NVDA insufficient, TSLA unavailable, and MSFT catalog-only; seven dated
macro series and all fixture surfaces retain `SIMULATED DATA` labels.

In another terminal, from the repository root:

```sh
cd apps/mobile
npm ci
EXPO_PUBLIC_AUTH_MODE=demo \
EXPO_PUBLIC_DEBATE_V2_ENABLED=true \
EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED=false \
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 \
  npx expo start --ios --localhost --clear
```

Use the workstation LAN IP for a physical phone, or `10.0.2.2` for the standard
Android Emulator. See the [mobile README](../apps/mobile/README.md) for client
compatibility and network setup. This synchronous fixture verifies layout and
canonical records; queued streaming/Stop/Continue need the standard profile.

## Runtime modes and flags

Plain defaults are `APP_DATA_MODE=standard`, `AUTH_MODE=demo`,
`PERSISTENCE_MODE=demo`, and `ANALYSIS_PROVIDER=demo`. Use explicit fixture mode
for a credential-free review when a configured root `.env` already exists.

| Setting | Default and behavior |
| --- | --- |
| `AUTH_MODE`, `PERSISTENCE_MODE` | `demo`; `supabase` enables real Auth and persistence |
| `ANALYSIS_PROVIDER` | `demo`; legacy JSON analysis can independently select `groq` or `gemini` |
| `DEBATE_WORKFLOW_V2` | `false`; enables owner-scoped `/debates` routes |
| `DEBATE_QUEUE_ENABLED` | `false`; when true, create/Challenge return `202` and bounded lifespan consumers execute the stage |
| `DEBATE_STREAMING_PROVIDER` | `deterministic`; independently selects live Bull/Bear `groq` streaming |
| `DEBATE_STREAMING_JUDGE_PROVIDER` | `deterministic`; independently selects live `groq` Interim/Final Judges |
| `DEBATE_INTERRUPTIONS_ENABLED` | `false`; enables Stop, before-output Stop, interjection, Continue/End and provider-attempt audit |
| `EXPLANATION_PROVIDER` | `deterministic`; optional read-only `groq` explanation |
| `REDIS_ENABLED` | `false`; optional public cache and admission/idempotency coordination |

V2 with Queue disabled is a synchronous deterministic preview (`201`);
`buffered_compatibility` events divide an already completed draft. With Queue
enabled, the Worker emits actual async deltas and persists validated complete
messages/citations. Round 1 has six alternating Turns plus an Interim Judge;
explicit Challenge then queues four Turns and a Final Judge. Live Turn and
Judge selections do not implicitly enable each other or Explanation.

Stop freezes the exact displayed prefix as an incomplete record and rotates
its generation into `interrupted_awaiting_user`. It also works before the first
output. Saving an interjection does not call a model; explicit Continue
requires that saved interjection, creates one new generation/Job, and keeps the
original frozen market snapshot. End settles cancellation. Old-generation
writes are rejected. Read-only Explanation accepts complete messages and the
eligible frozen incomplete prefix without promoting partial text to evidence.

`GET /debates/{id}/provider-attempts` exposes owner-scoped dispatch/outcome and
reported/unknown usage when interruptions are enabled. It remains the audit
source because V2 in-app model/token diagnostics are not implemented.

The [API contract](../docs/api/api-contract.md) specifies bodies, status codes,
SSE resume, admission limits and failure semantics. The
[agent workflow](../docs/agents/agent-workflow.md) covers grounding/validation.

## Standard Supabase/live profile

Apply the base schema and ordered migrations, including Queue and interruption
RPC/security fixes, before enabling their flags. Follow the
[Supabase setup](supabase/README.md) and
[live services guide](../docs/setup/live-services.md). Standard V2 writes use
the backend-only `SUPABASE_SECRET_KEY`; never expose it through Expo public
configuration. User-facing reads remain owner-scoped and protected by RLS.

The complete two-terminal live profile is maintained in the
[V2 resume checklist](../docs/planning/v2-beta-resume-checklist.md). It uses a
dedicated test user, one API/Worker/SSE process, one Worker, a one-attempt Job
budget, and a 61-second provider pacer. Do not use hot reload during a live
Session. Cached-data freshness and actual account quotas must be checked at
run time; historical live proofs do not establish today's data freshness.

A standalone consumer is available from `backend/`:

```sh
.venv/bin/python -m app.debate_worker_main
```

The supported live topology keeps the Worker and SSE broker in the API process.
A standalone Worker does not deliver transient deltas to another process's
broker. Do not add it alongside lifespan consumers unless extra concurrency
and that stream limitation are intentional. Docker starts one Uvicorn Worker.

## Optional cache and admission

Redis uses bounded timeouts with a process-local fallback. It never replaces
canonical Supabase data or Queue transport. Stock search is cached for 30
minutes, the public bundle core for five minutes, and eligible default V2
factor snapshots for six hours. The latest quote is resolved outside the bundle
cache; custom questions/context bypass shared snapshot caching. Generated
Debate messages and owner history are never shared cache entries.

`X-Cache-Status` reports `BYPASS`, `MISS`, `HIT`, or `DEGRADED`.
`GET /health/cache?probe=true` performs a bounded connectivity probe without
exposing connection secrets. V2 admission defaults to one non-terminal Debate
per user and three new admissions/hour; Explanation has a separate 12/hour
limit. Duplicate queued idempotency replays do not consume a new slot.

## Verification

From the repository root:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
PYTHONPATH=backend backend/.venv/bin/python scripts/benchmark_stock_search_cache.py
```

The 2026-10-17 suite passes **542 tests**. Tests isolate settings and mock
external services. Hosted verifiers and scripts with `--confirm-live-quota`
are separate opt-in checks; they are not ordinary unit tests. The current
[verification record](../docs/planning/phase-8-verification-record.md) separates
local results, historical hosted proof and remaining manual acceptance.

## Ingestion

Run ingestion from the repository root using the backend virtual environment:

| Script under `scripts/` | Purpose |
| --- | --- |
| `ingest_rss.py --ticker AAPL --url https://example.com/feed.xml` | Print normalized RSS evidence for review |
| `ingest_live_evidence.py` | Upsert configured RSS, SEC narrative chunks and structured XBRL facts |
| `ingest_live_prices.py` | Refresh completed daily OHLCV; AAPL and one provider call by default |
| `ingest_aapl_weekly_history.py` | Refresh labelled weekly history |
| `ingest_macro_context.py` | Refresh dated FRED/EIA macro observations |

For example:

```sh
PYTHONPATH=backend backend/.venv/bin/python scripts/ingest_live_prices.py
```

Ingestion requires the appropriate server-side provider credentials and
Supabase secret. SEC calls also require a declared `SEC_USER_AGENT`. Daily
price refreshes have a hard three-call cap and preserve previous rows on a
failed ticker; missing/stale prices must remain labelled in the API. Finnhub
quotes are separate, cached for 60 seconds per backend instance. Scheduled
refresh workflows live in `.github/workflows/`; no ingestion runs on a stock
search. See the live services guide for per-source budgets and verifier cleanup.
