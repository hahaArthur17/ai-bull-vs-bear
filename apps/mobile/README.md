# Mobile app

Last reviewed: 2026-10-17.

Expo / React Native client for AI Bull vs Bear, targeting Expo SDK54
(`expo 54.0.37`, React Native `0.81.5`, React `19.1.0`). The project owner
reports the simulator flow is working; **physical-device testing has not been
performed**. Local automated verification passes 122 tests, TypeScript, Expo
Doctor 18/18, and Web/iOS/Android exports. Exports are bundle checks, not native
runtime or physical-device acceptance.

## Prerequisites

Use Node.js **24** and npm (the runtime used for the current local checks and
CI). The locked Supabase packages require Node >=22; the test script also uses
Node's built-in TypeScript support, so the old Node 20 CI setup is obsolete.
Install Xcode for the iOS Simulator or Android Studio for the Android Emulator.

The project remains on SDK54. Expo Go supports the latest SDK, so verify client
compatibility instead of assuming the current App Store client supports SDK54.
Matching older Expo Go clients can be obtained for Android and iOS Simulator
from [expo.dev/go](https://expo.dev/go). A physical iPhone can install only the
current App Store Expo Go; use an SDK54 development build if incompatible. See
[Expo's compatibility guidance](https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/)
and [development-build setup](https://docs.expo.dev/develop/development-builds/create-a-build/).

## Credential-free simulator review

Start the explicit deterministic fixture from the repository root:

```sh
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
ENVIRONMENT=development APP_DATA_MODE=review_fixture \
  .venv/bin/python -m uvicorn app.main:app \
  --reload --host 0.0.0.0 --port 8000
```

In a second terminal, from the repository root:

```sh
cd apps/mobile
npm ci
EXPO_PUBLIC_AUTH_MODE=demo \
EXPO_PUBLIC_DEBATE_V2_ENABLED=true \
EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED=false \
EXPO_PUBLIC_API_URL=http://127.0.0.1:8000 \
  npx expo start --ios --localhost --clear
```

The API fixture overrides any live credentials in the ignored root `.env` and
uses in-memory stores with deterministic providers. It needs no Supabase or
model key. All fixture market/evidence surfaces must show `SIMULATED DATA`.
V2 completes synchronously here; this profile does not prove queued streaming
or Stop/Continue behavior.

Use the API address appropriate to the client:

| Client | `EXPO_PUBLIC_API_URL` | Metro command |
| --- | --- | --- |
| iOS Simulator on the API's Mac | `http://127.0.0.1:8000` | `npx expo start --ios --localhost --clear` |
| Standard Android Emulator | `http://10.0.2.2:8000` | `npx expo start --android --clear` |
| Physical phone on the same Wi-Fi | `http://YOUR_COMPUTER_LAN_IP:8000` | `npx expo start --lan --clear` |
| Local Web compatibility check | `http://localhost:8000` | `npm run web` |

For a phone, the backend must listen on `--host 0.0.0.0` as above. `localhost`
on a phone means the phone itself. Find the workstation LAN IP using the active
network interface (`ipconfig getifaddr en0` commonly works for macOS Wi-Fi).
Keep API and Metro running, allow local-network access, and open the QR/deep
link with the iPhone Camera or the compatible client's scanner. A Metro tunnel
does not expose port 8000; the API still needs a reachable URL.

For a development build, use `npx expo start --dev-client --lan --clear` once
that build is installed. Record device/OS/client versions and the launched
commit when performing the pending physical-device pass.

## Standard Supabase and live Debate

Use the complete profile in the
[V2 beta resume checklist](../../docs/planning/v2-beta-resume-checklist.md)
after applying migrations and checking freshness/quotas in the
[live services guide](../../docs/setup/live-services.md).

The client and backend must agree on flags:

| Client variable | Matching backend configuration |
| --- | --- |
| `EXPO_PUBLIC_AUTH_MODE=demo` | `AUTH_MODE=demo` |
| `EXPO_PUBLIC_AUTH_MODE=supabase` | `AUTH_MODE=supabase`, public Supabase URL/key present |
| `EXPO_PUBLIC_DEBATE_V2_ENABLED=true` | `DEBATE_WORKFLOW_V2=true` |
| `EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED=true` | `DEBATE_INTERRUPTIONS_ENABLED=true`; Continue additionally requires Queue |
| `EXPO_PUBLIC_API_TIMEOUT_MS=45000` | Controlled local/live acceptance timeout; default is 15000 ms |

`app.config.js` reads the ignored root `.env`; public Supabase configuration
can use `EXPO_PUBLIC_SUPABASE_URL` and `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`,
or the legacy anon-key variable. The config also maps root `SUPABASE_URL` and
`SUPABASE_ANON_KEY` for local compatibility. `EXPO_PUBLIC_AUTH_MODE=demo`
explicitly bypasses client Auth during fixture review. Restart Metro after
changing environment configuration. Never place server secrets or provider
keys in an `EXPO_PUBLIC_` variable.

The saved AAPL interaction Session is **complete**. Reopen it through History
for visual checks; do not submit another Round 2 to it. A fresh live Session
can spend model quota, and the historical transcript predates part of the
source-quote guard. V2 in-app provider/token diagnostics and hosted History
reopen timing remain follow-ups.

## Implemented flow

Sign in → catalog search / Watchlist → Stock Detail and Signals → Evidence
Board → Debate → read-only Explanation or explicit Round 2 → History.
Legacy single-response analysis and fixed claim examination remain available
when V2 is off. The About surface and educational-use disclaimer remain visible.

Search is debounced through the FastAPI catalog. Coverage labels distinguish
7,695 identities from four curated `debate_ready` examples. A `catalog_only`
identity can be saved and opened without fetching prices, evidence, or Debate.
Live AAPL evidence does not establish equal current-data coverage for every
curated ticker.

The V2 screen consumes authenticated XHR SSE, reconnects from ordered cursors,
and reloads canonical state after cursor expiry or interruption. Temporary
provider text is separate from durable messages. One active bubble reveals
text progressively; completed live messages finish revealing before later
messages appear, while saved History loads directly. Display pacing does not
prevent the backend from admitting a later model request.

With interruptions enabled, Stop retains the visible prefix or stops before
first output, then allows read-only Explanation, saved interjection, explicit
Continue, or End. Saving a point does not dispatch a model. Pending Stop state
is isolated by account/session, and account changes reset the app workspace
and reject stale former-account responses. Device lifecycle and weak-network
acceptance still require recorded manual evidence.

## Source layout

| Path | Responsibility |
| --- | --- |
| `App.tsx` | Authentication, account-scoped state, navigation and API orchestration |
| `src/api.ts`, `src/types.ts` | Typed HTTP boundary and data contracts |
| `src/debateStream.ts` | Authenticated SSE parsing, resume and canonical recovery |
| `src/revealScheduler.ts` | Ordered reveal of received text |
| `src/pendingInterruption.ts` | Account/session-scoped pending Stop storage |
| `src/screens/` | Watchlist, research, Evidence, Examination, Legacy/V2 Debate, History, About |
| `src/components/`, `src/components/debate/` | Shared controls, messages, evidence and Judge presentation |
| `src/theme/tokens.ts` | Shared deep-navy semantic design tokens, safe areas, focus and motion |
| `src/research/` | Chart calculations and responsive research layout |

## Verification

From `apps/mobile/` after `npm ci`:

```sh
npm run test:stream
npm run typecheck
npm run build:web
npx expo-doctor
npx expo export --platform ios --output-dir dist/ios
npx expo export --platform android --output-dir dist/android
```

`test:stream` is the historical script name for **all** `src/*.test.ts` tests,
including research, Auth, accessibility, reveal and recovery tests. The current
122 tests pass. Export directories are ignored and must not be committed.

Dependency advisories are captured in the
[verification record](../../docs/planning/phase-8-verification-record.md);
rerun `npm audit` for a current result. Native acceptance covers safe-area and
Android edge-to-edge/system bars, keyboard/back behavior, text scaling,
accessibility, reconnect/background/force reopen, and the complete Debate flow.
See the [UI acceptance matrix](../../docs/planning/phase-8-ui-acceptance-matrix.md).
