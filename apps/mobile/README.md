# Mobile app

This is the Expo / React Native client for AI Bull vs Bear. The current baseline
targets Expo SDK 54 (`expo 54.0.37`, React Native `0.81.5`, React `19.1.0`). It
uses the deterministic FastAPI demo provider by default and does not require
API keys.

The SDK54 automated baseline passes 112 mobile tests, TypeScript typecheck, Expo
Web export, Expo Doctor 18/18, and iOS and Android native bundle exports. These
checks do not replace physical-device acceptance.

## Run on an iPhone with App Store Expo Go

Start the backend so another device on the same network can reach it:

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ENVIRONMENT=development APP_DATA_MODE=review_fixture \
      uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Find the computer's LAN IPv4 address (for example, `192.168.1.20`) and start
Expo in another terminal. Replace the example address with the real address:

    cd apps/mobile
    npm ci
    EXPO_PUBLIC_AUTH_MODE=demo \
    EXPO_PUBLIC_DEBATE_V2_ENABLED=true \
    EXPO_PUBLIC_API_URL=http://192.168.1.20:8000 \
    npx expo start --lan --clear

Then on the iPhone:

1. Install and open **Expo Go** from the Apple App Store. It must be the
   SDK54-compatible client.
2. Put the iPhone and computer on the same Wi-Fi network, and allow Expo Go
   local-network and camera access when iOS asks.
3. In Expo Go, choose **Scan QR code** and scan the QR code shown by the
   `npx expo start --lan` terminal.
4. Keep the backend and Metro terminals running during the review.

For a physical iPhone, `EXPO_PUBLIC_API_URL` must use the computer's LAN IP.
Do not use `localhost` or `127.0.0.1`: on a phone those addresses point back to
the phone itself. Loopback is suitable only when the app and backend run in the
same simulator environment. On macOS, `ipconfig getifaddr en0` commonly prints
the Wi-Fi address; use the active interface if it differs.

This iPhone run is the next acceptance entry for commit `0f70366`; record the
exact iPhone model, iOS version, and Expo Go App Store version. Android remains a
separate native regression surface even though its bundle export passes; use a
native simulator or an available Android device for that follow-up.

## Implemented flow

Security catalog search -> Watchlist -> Stock detail -> Technical indicators ->
Evidence board -> Bull vs Bear analysis -> Claim cross-examination.

Search is debounced and handled by the FastAPI catalog endpoint rather than by
filtering four client-side rows. Every result displays coverage. A
`catalog_only` identity can be saved and opened, but its detail screen explicitly
omits prices, evidence, technical signals, and Debate; opening it does not load
the market-data bundle.

The current analysis screen still waits for one complete API response. A
`DebateStreamClient` module now provides authenticated XHR SSE consumption for
Web/React Native, fragmented-frame parsing, ordered resume, temporary draft
text, canonical completion replacement, and expired-cursor reload. The
default-off V2 screen mounts that client and renders Queue/Worker/retry state,
canonical messages, generation-scoped cancellation, and an exact-passage Round
2 Challenge. Its complete-message term chips now open a separate, read-only
Explanation panel that uses the authenticated HTTP boundary without changing
the Debate. V2 History refreshes owner-scoped canonical sessions and labels a
durable Final Judge summary before reopening its transcript. The production flag
remains off; cross-process transient replay, physical-device checks, and the remaining financial-technology redesign stay in the canonical
[`portfolio implementation plan`](../../docs/planning/portfolio-implementation-plan.md).

Semantic colours, typography, spacing, radii, elevation, breakpoints,
interaction targets, and motion rules live in `src/theme/tokens.ts` and are
re-exported through `src/theme.ts`. The existing app styles continue to use the
compatibility palette while screens migrate in their own redesign slices.
Reusable base UI components live under `src/components/`. Watchlist, History,
About, Stock detail/charting, Evidence, Examination, Legacy Debate, and V2
Debate are standalone screen modules under `src/screens/`. Shared Legacy
Debate presentation, including Claim Cards, Judge summaries, agent status, and
evidence citations, lives in `src/components/debate/`. `App.tsx` retains only
app-level authentication, state, navigation, and API orchestration.

The mobile app intentionally presents analysis as educational context and
always shows the financial-advice disclaimer.
