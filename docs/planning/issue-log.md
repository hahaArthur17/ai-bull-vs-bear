# Project Issue Log

This is the append-only record of material project issues. It preserves the
facts needed for status reports and for a future maintainer to resume an
investigation without relying on chat context.

## How to record an issue

Add a dated entry whenever an incident, data-integrity defect, deployment
failure, access-control problem, or external-provider limitation materially
affects the project. Record:

- the user-visible symptom and affected scope;
- verified evidence and the current confidence in the diagnosis;
- mitigation, verification, and the commit or configuration change involved;
- the remaining follow-up and its owner.

Do not include API keys, tokens, passwords, service-role credentials, or other
secrets. Link to an existing weekly report for broader context rather than
duplicating implementation detail.

---

## 2026-08-21 — Debate view crashed on timestamp-formatted evidence dates

**Status:** Remediation implemented; production verification pending.

**Symptom and impact**

- Pressing **Run analysis** could produce `RangeError: Invalid time value` and
  leave the web Debate view blank.
- The error was raised while rendering dated citations, not while generating
  Bull, Bear, or Judge content.

**Verified evidence and diagnosis**

- A read-only production response-shape audit confirmed that saved Debate
  evidence uses complete ISO 8601 `published_at` timestamps, while macro
  `observation_date` values are date-only.
- The mobile `formatMarketDate` helper appended `T12:00:00Z` to every input.
  This converted a valid evidence timestamp into an invalid string with two
  time components, and `Intl.DateTimeFormat` threw during the citation map.
- The macro context itself is available to real Groq/Gemini provider prompts.
  Production currently uses the deterministic demo provider, whose Bull/Bear
  text had not previously made the same dated background explicit.

**Remediation**

- `853527a` separates date formatting into a defensive helper. It parses
  `YYYY-MM-DD` market dates and complete ISO timestamps correctly, and shows a
  safe unavailable label instead of crashing for missing or malformed values.
- `1d7ef8b` adds the complete close-date-bounded macro background to demo Bull
  and Bear text with explicit non-causation language. It remains background,
  not claim evidence, and does not weaken the no-current-news safety cap.
- Full backend tests (78), mobile TypeScript checks, and Web export pass before
  deployment.

**Follow-up**

- Verify the deployed static site by running an AAPL Debate and confirming the
  page renders dated citations plus the macro-background statement.

**Related code**

- `apps/mobile/src/dateFormat.ts`
- `apps/mobile/App.tsx`
- `backend/app/services/analysis.py`

---

## 2026-08-21 — Legacy analysis history causes production `/analysis` 500

**Status:** Resolved and production-verified.

**Symptom and impact**

- The production web app reported a CORS failure while requesting `GET
  /analysis`, accompanied by an HTTP `500` response.
- The home screen cannot reliably load a signed-in user's saved analysis
  history while an incompatible historical record is present.

**Verified evidence**

- Production CORS is correctly configured for
  `https://ai-bull-vs-bear.onrender.com`: an `OPTIONS /analysis` preflight and
  an unauthenticated `GET /analysis` both return the expected
  `Access-Control-Allow-Origin` response header.
- A read-only, aggregate-only audit of stored `agent_outputs` found six saved
  `response` records. Five predate the immutable analysis-snapshot contract and
  omit the now-required `snapshot` object; one current-format record parses.
- `SupabaseStore.list_analyses()` calls `AnalysisResponse.model_validate()` for
  every stored response without handling validation failures. A legacy record
  therefore raises an unhandled validation error and turns the endpoint into a
  `500`.
- The browser's CORS message is secondary: FastAPI's outer server-error path
  generates that unhandled `500` outside the currently added CORS middleware,
  so the error response has no CORS header for the browser to read.

**Data-integrity decision**

Do not fabricate a current-price snapshot for historical analyses and do not
delete the old rows. Those records lack the immutable market-close/evidence
metadata required to represent them as equivalent to a current-format Debate.

**Required remediation**

1. Make analysis-history reads backward compatible: skip or explicitly label
   non-reproducible legacy records instead of letting one invalid row fail the
   entire list. Apply the same handling to a direct request for a legacy record.
2. Wrap the whole FastAPI application with CORS so that unexpected `500`
   responses still return the permitted-origin header and expose a readable API
   error rather than a misleading browser-only CORS failure.
3. Add regression tests containing a pre-snapshot stored response and verify
   that valid current-format history remains accessible.

**Local remediation completed**

- `b53dc6f` makes persisted-history parsing tolerant of legacy records. They
  remain stored but are omitted from current-format history and direct legacy
  lookups return no current-format response.
- `76e9464` wraps the complete FastAPI application in CORS middleware, so an
  unexpected server error still returns the permitted-origin header.
- The new legacy-history and unexpected-error CORS regression tests pass; the
  full backend suite passes 78 tests.

**Production verification**

- Render auto-deployed commit `039caf0` and marked the service live.
- Public `/health` returns `200`.
- An authenticated, origin-bearing production request to `/analysis` returns
  `200` and the expected `Access-Control-Allow-Origin` value. It returns the
  one current-format stored record; the five incompatible legacy records remain
  intact in storage and do not interrupt the response.

**Related code**

- `backend/app/services/supabase_store.py`
- `backend/app/main.py`
- [`reports/project-week-06.md`](reports/project-week-06.md)

---

## 2026-08-21 — Render deployment health-check timeout

**Status:** Resolved by redeploy; root cause not proven.

**Symptom and impact**

- Render marked deployment commit `1e15a7d` (`feat(analysis): snapshot
  non-causal macro context`) as failed after its internal health check timed
  out at `/health`.
- The previous live release remained serving, so the immutable macro snapshot
  feature and later main-branch changes were not yet available in production.

**Verified evidence**

- The failed Render deployment completed its image build, then timed out during
  the deploy/health-check phase. Its visible logs did not contain a Python
  traceback or Uvicorn startup failure.
- A local production-style launch of the same FastAPI application started
  successfully and returned `200` from `/health`.
- A user-approved manual deployment of latest `main` (commit `18f7e45`)
  subsequently started Uvicorn, completed application startup, received
  repeated Render `GET /health` responses with `200 OK`, and reached the
  Render `live` state.
- An independent public check confirmed `/health` and confirmed that the
  production OpenAPI `AnalysisSnapshot` schema includes `macro_context`.

**Diagnosis**

The available evidence is more consistent with a transient Render deployment
or health-check transition failure than with a reproducible application-start
defect. This is an inference, not a confirmed platform root cause: retain the
failed deployment logs if the problem recurs.

**Mitigation and verification**

- Performed one normal manual “Deploy latest commit” action only; no environment
  variables, service settings, or build cache were changed.
- Render logs verified a healthy Uvicorn process and successful health checks.
- Public verification: `https://ai-bull-vs-bear-api.onrender.com/health`.

**Follow-up**

- If another deploy times out, capture its full runtime logs and compare its
  startup timestamp, bound port, and `/health` request records before changing
  code or clearing the build cache.
- Add an uptime/health monitor during release preparation (Week 5) so an
  unavailable production API is detected outside the deployment dashboard.

**Related records**

- [`reports/project-week-06.md`](reports/project-week-06.md)
- [`weekly-roadmap.md`](weekly-roadmap.md)
