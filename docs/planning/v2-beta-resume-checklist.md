# V2 Beta Resume Checklist

Last updated: 2026-09-17. This is the practical handoff for the next local
Expo V2 beta session. It complements the broader
[WP8L route](wp8l-next-steps.md); use this file first when resuming the current
manual test.

## Current position

- SDK54 Expo Go/simulator UI review, real-data display, and a Legacy Groq smoke
  have been completed locally.
- A saved, authenticated AAPL V2 Round 1 is currently `awaiting_user`, has
  seven canonical records (three Bull turns, three Bear turns, and the Interim
  Judge), and has no active Queue Job. Resume this Session from **History**;
  do not create another Round 1 merely to continue it.
- A separate V2 session failed safely during a Bear provider attempt before any
  replayable Bear text. Its completed Bull message was preserved. The mobile
  fix in `1166e67` prevents an empty `turn.started` placeholder from looking
  like a chat message that vanished. See [issue-log.md](issue-log.md).
- The V2 mobile UI does not yet show provider-attempt model/token diagnostics.
  Do not treat that as verified in the UI. The backend ledger remains the
  source of truth, and the read-only V2 diagnostics view is still a follow-up.
- Redis is intentionally disabled in this local profile. It is not required
  for the V2 flow and does not fix the saved-Debate detail-read latency.
- Opening a saved Debate currently waits for its canonical detail before the
  screen navigates. It is a known performance issue, not a new model call or a
  data-integrity failure. See the corresponding issue-log entry.

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

## Next test — complete the saved normal path

This is the highest-priority next action. It reuses the saved Round 1 and does
not repeat its seven provider attempts.

1. In the app, open **History** → the saved AAPL card → **Open interim
   assessment**. A short wait is currently expected because the server loads
   the canonical Session, messages, citations, and Job before navigation.
2. Confirm all seven Round 1 records are present, ordered, and attributed
   correctly: three Bull turns, three Bear turns, then the Interim Judge.
   Expand several citations and check source, date, freshness, and support
   passage. Confirm the stock/date snapshot is the saved one, not a simulated
   fixture.
3. Use one point Explanation/read-only question. With the profile above it
   uses the deterministic Explanation provider and does not add a Debate turn
   or spend a Groq Debate call.
4. If those checks pass and the remaining model budget is accepted, use the
   on-screen explicit question/Continue flow to start Round 2. Round 2 makes
   five further live provider requests (four Bull/Bear turns and the Final
   Judge), paced at least 61 seconds apart. Do not start a second Session at
   the same time.
5. Confirm the Final Judge appears, the Session becomes `completed`, and
   History reopens the same final transcript and citations without duplicate or
   reordered messages.

While observing live output, a temporary larger word burst can occur when the
provider or durable checkpoint batching outruns the display scheduler. It is
acceptable only if text remains ordered, no words are lost/duplicated, and one
active draft bubble is shown. Record a screenshot and approximate time if whole
paragraphs jump in at once, content becomes unordered, or a canonical message
changes after completion.

## After the normal path passes

Run these as separate, deliberate device tests; do not combine them with the
normal completion run.

1. **Stop and recovery:** Stop before first visible text and mid-stream; verify
   the visible prefix, saved waiting state, and no automatic continuation.
2. **Interjection:** save a user point, verify it is not promoted to market
   evidence, then explicitly Continue or End.
3. **Resilience:** background/foreground the app, reopen History, and test a
   reconnect. Confirm no duplicate messages or replayed hidden text.
4. **V2 diagnostics implementation:** add the safe provider-attempt
   model/usage read model to the mobile UI before claiming in-app V2 token
   verification.
5. **Performance work:** replace the serial saved-Debate detail reads with a
   bounded owner-scoped aggregate read. This is independent from Redis and
   should follow functional acceptance unless the delay blocks usability.

## Completion boundary for this beta pass

The V2 normal-path device beta is sufficiently evidenced when the saved Round
1 and one deliberately continued Round 2 reach the Final Judge; citations,
History reload, ordering, real-data labels, and safe provider failures behave
as stated above. It does **not** complete the Stop/reconnect/native
accessibility/performance tasks or the missing V2 in-app token diagnostics.
