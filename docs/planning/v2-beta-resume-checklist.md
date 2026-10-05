# V2 Beta Resume Checklist

Last updated: 2026-10-05. This is the practical handoff for the next local
Expo V2 beta session. It complements the broader
[WP8L route](wp8l-next-steps.md); use this file first when resuming the current
manual test.

## Current position

- SDK54 Expo Go/simulator UI review, real-data display, and a Legacy Groq
  smoke were completed locally before the Oct 5 UI simplification.
- A newer authenticated AAPL V2 Session
  `2b6831a2-2f33-5629-bdcc-a403c9ec9c2b` completed both rounds with real
  model calls. Stop → Explanation → user interjection → Continue was exercised
  in Round 1 and Round 2; Final Judge and History reopen were observed. The
  17 canonical records include two incomplete prefixes. This Session is
  complete; do not Continue it or create a duplicate to repeat the proof.
- An initial live attempt failed safely during stream finalization, and an
  older Bear attempt failed before replayable text. Keep these terminal
  Sessions as test records. See [issue-log.md](issue-log.md).
- The V2 mobile UI does not yet show provider-attempt model/token diagnostics.
  Do not treat that as verified in the UI. The backend ledger remains the
  source of truth, and the read-only V2 diagnostics view is still a follow-up.
- Redis is intentionally disabled in this local profile. It is not required
  for the V2 flow and does not fix the saved-Debate detail-read latency.
- Saved Debate detail now has a bounded owner-checked message/citation read in
  code, but cold/warm hosted reopen latency has not been remeasured.
- The completed AAPL Session includes a message saved before the new
  source-quote guard was active. It is an interaction proof, not proof that
  every source claim in that old transcript is verified.

## Start the local V2 beta profile

Use two terminals. These commands contain no secrets; they read required
Supabase and Groq credentials from the ignored root `.env` file. Do not add a
secret, access token, or password to this document or the shell command.

### Terminal A — API, Queue Worker, and SSE

```sh
cd "/Users/miao/Documents/BSemester576/AI Bull vs Bear/ai-bull-vs-bear/backend"

ENVIRONMENT=development \
APP_DATA_MODE=standard \
AUTH_MODE=supabase \
PERSISTENCE_MODE=supabase \
ANALYSIS_PROVIDER=demo \
DEBATE_WORKFLOW_V2=true \
DEBATE_QUEUE_ENABLED=true \
DEBATE_INTERRUPTIONS_ENABLED=true \
DEBATE_JOB_MAX_ATTEMPTS=1 \
DEBATE_WORKER_CONCURRENCY=1 \
DEBATE_PROVIDER_MIN_INTERVAL_SECONDS=61 \
DEBATE_STREAMING_PROVIDER=groq \
DEBATE_STREAMING_JUDGE_PROVIDER=groq \
DEBATE_GROQ_MODEL=openai/gpt-oss-20b \
DEBATE_JUDGE_GROQ_MODEL=openai/gpt-oss-20b \
EXPLANATION_PROVIDER=deterministic \
APP_BUILD_SHA=$(git rev-parse HEAD) \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep this process running. Do not add `--reload`: it can restart a
quota-bearing Worker. `DEBATE_JOB_MAX_ATTEMPTS=1` means one Worker attempt per
round Job, not one Debate Session and not one model call for the entire
Debate. A provider failure is recorded safely instead of being automatically
retried.

### Terminal B — iOS Simulator Expo client

```sh
cd "/Users/miao/Documents/BSemester576/AI Bull vs Bear/ai-bull-vs-bear/apps/mobile"

EXPO_PUBLIC_AUTH_MODE=supabase \
EXPO_PUBLIC_DEBATE_V2_ENABLED=true \
EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED=true \
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 \
EXPO_PUBLIC_API_TIMEOUT_MS=45000 \
npx expo start --ios --clear
```

For a physical phone, replace `127.0.0.1` with the computer's LAN IP and use
`npx expo start --lan --clear`. A phone's `localhost` is the phone itself, not
the computer.

Before a new model-bearing action, visit `http://127.0.0.1:8000/health` and
confirm `data_mode` is `standard`, `debate_workflow_v2` is `true`, and the
reported build SHA is the commit you intentionally launched.

## Next test — device and post-guard acceptance

The complete live interaction path has been observed. The next checks should
use the target simulator or device and record the running backend SHA; do not
spend another full model run merely to inspect layout or History.

1. Reopen the completed AAPL Session from **History**. Verify all 17 canonical
   records, both incomplete prefixes, the Final Judge, ordering, citation
   cards, and the visible warning for earlier Groq v1 content. Measure cold
   and warm reopen time separately.
2. Scroll the full AAPL Stock Detail screen at narrow width, including every
   technical and macro panel; then inspect Watchlist search, saved rows,
   empty/error states, and large text. Record any collision or clipping.
3. Exercise sign-up/confirmation and switch between two test accounts while a
   home or stock request is delayed. Verify Watchlist and Debate History stay
   account-scoped and no former-account content flashes in the new workspace.
4. On a new deliberately budgeted Session, verify the current source guard
   against actual evidence excerpts and repeat Stop/recovery during app
   background/foreground and a weak connection. Keep the resulting Session ID,
   build SHA, and provider-attempt ledger; do not record credentials.

While observing live output, a temporary larger word burst can occur when the
provider or durable checkpoint batching outruns the display scheduler. It is
acceptable only if text remains ordered, no words are lost/duplicated, and one
active draft bubble is shown. Record a screenshot and approximate time if whole
paragraphs jump in at once, content becomes unordered, or a canonical message
changes after completion.

## Remaining implementation and measurement

1. Add safe V2 provider-attempt model/usage diagnostics to the mobile UI and
   reconcile reported and unknown usage with the backend ledger.
2. Measure the new saved-Debate detail path on hosted Supabase, cold and warm,
   and compare canonical messages/citations against the saved Session.
3. Finish native accessibility, weak-network, account-switch, and product-owner
   visual acceptance. A post-guard source audit needs a fresh model Session.

## Completion boundary for this beta pass

The completed live AAPL run establishes the controlled interaction path through
both rounds, including two Stop/interjection/Continue cycles and History
reopen. It does **not** complete target-device acceptance, a wholly post-guard
source audit, registration/two-account acceptance, weak-network recovery,
hosted reopen performance, or the missing V2 in-app token diagnostics.
