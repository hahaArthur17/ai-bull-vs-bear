# Zero-Cost Demo Deployment

Last verified: 2026-08-16

## Non-negotiable rule

The demo must remain at **NZD/USD 0**. Do not add a payment method, enable a
paid plan, attach a paid disk, buy an add-on, or enable usage-based overages.
If a free quota is exhausted, the acceptable behaviour is degraded demo data
or temporary suspension until the quota resets.

## Selected architecture

- Render Static Site serves the Expo Web export.
- One Render Free web service runs the FastAPI Docker image.
- The existing Supabase Free project provides Auth, Postgres, pgvector, and
  persistent data. No Render database or persistent disk is created.
- Production sets `ANALYSIS_PROVIDER=demo`. Bull, Bear, and Judge responses are
  deterministic and consume no Groq or Gemini tokens.
- Pytest forces demo auth, persistence, and analysis settings before importing
  the application, so a developer's local `.env` cannot make tests call live
  Supabase or model providers.
- Prices and evidence are read from Supabase caches. Missing or unavailable
  data falls back to the deterministic demo dataset.

The root `render.yaml` creates only the free web service and free static site.
The root `Dockerfile` installs `backend/requirements-runtime.txt`, which omits
test tools and unused model SDKs.

## Measured fit

| Item | Local production-equivalent measurement | Free limit / interpretation |
| --- | ---: | --- |
| FastAPI runtime virtual environment | 30 MB | Small relative to the image and host limits |
| FastAPI health-check peak RSS | 56,033,280 bytes (about 53.4 MiB) | About 10.4% of Render Free's 512 MB RAM |
| Backend source copied into image | 316 KB | Negligible |
| Expo Web export | 616 KB, 3 files | Suitable for a static CDN |
| Render Free compute | one 0.1 CPU / 512 MB service | One service fits within 750 instance-hours/month |

The development folders are much larger (`backend/.venv` about 244 MB and
`apps/mobile/node_modules` about 348 MB), but `.dockerignore` excludes them.
They are not copied into the backend image.

Render sleeps the API after 15 idle minutes and cold start can take about one
minute. The production frontend therefore uses a 75-second request timeout.

## External-service budget

| Service | Free allowance relevant to this demo | Enforced demo use |
| --- | --- | --- |
| Render | 750 free web-service hours/workspace/month; free static site | One backend only; `plan: free`; no payment method, so limit exhaustion suspends instead of billing |
| Supabase | 500 MB database, 50,000 MAU, 5 GB egress, 5 GB cached egress, 1 GB file storage | Existing small dataset; no file uploads; never upgrade from Free |
| Alpha Vantage | 25 requests/day | Three tickers (`AAPL,NVDA,TSLA`), maximum 3 provider calls per invocation, one daily invocation, and no retry in the batch command |
| Groq / Gemini | Provider-specific free rate limits | 0 production requests because `ANALYSIS_PROVIDER=demo` |
| Apify | $5/month Free prepaid usage, no card required | Disabled; 0 production runs until a concrete Actor is justified |
| Finnhub | Free account has request limits and incomplete free historical coverage | Disabled; 0 production calls |
| SEC EDGAR / RSS | No paid runtime dependency | 0 requests in the web request path; refresh only through a deliberate offline ingestion run |

The price command's three-call cap is enforced in code. The once-per-day rule
is an operating rule because free Render does not provide free cron jobs. Do
not expose this command as a public endpoint.

Automated tests are also part of the zero-call boundary. Run provider-specific
tests only with mocks; use a separate deliberate manual command for any live
model verification.

## Deploy without exposing server credentials

1. Push the repository and open Render's **New Blueprint** flow.
2. Connect the repository containing `render.yaml`.
3. Confirm that `ai-bull-vs-bear-api` shows the **Free** instance type and
   `ai-bull-vs-bear` shows **Static Site**. Stop if Render proposes any paid
   resource.
4. Leave the Render workspace without a payment method. This converts monthly
   bandwidth exhaustion into suspension instead of an overage charge.
5. Fill only these Blueprint values:

   - backend `CORS_ORIGINS`: the final static-site HTTPS URL;
   - backend `SUPABASE_URL` and `SUPABASE_ANON_KEY`;
   - frontend `EXPO_PUBLIC_SUPABASE_URL` and
     `EXPO_PUBLIC_SUPABASE_ANON_KEY`.

6. Do **not** add `SUPABASE_SECRET_KEY`, SEC, Alpha Vantage, Apify, Finnhub,
   Groq, Gemini, or RLS-test-user credentials to either Render service.
7. After both deploys complete, open `/health`, sign in with a disposable test
   user, run one analysis, reload, and confirm that history persists.

The Supabase URL and anon/publishable key are intentionally public client
configuration. Row Level Security remains the authorization boundary. The
server secret and all provider keys must stay out of the frontend bundle.

## Failure behaviour for the presentation

- Wake the backend by opening its `/health` URL about one minute before the
  presentation.
- If Alpha Vantage is unavailable or unconfigured, the UI clearly labels and
  uses `demo_fallback` prices.
- If cached evidence retrieval fails, deterministic evidence remains available.
- Model quota cannot interrupt the demo because the deployed analysis provider
  is deterministic.
- If a free hosting quota is exhausted, wait for the reset; do not upgrade.

## Post-deploy acceptance checks

- `GET /health` returns `status=ok`, `environment=production`, and
  `provider=demo`.
- The frontend can list stocks and open AAPL, NVDA, and TSLA detail screens.
- Login, watchlist changes, analysis creation, and reload persistence work.
- Browser network requests contain the public Supabase key only; no server-only
  credential appears in the JavaScript bundle or request payloads.
- Render Billing still shows no payment method and no paid services.
