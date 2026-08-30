# Mobile app

This is the Expo / React Native client for AI Bull vs Bear. It uses the
deterministic FastAPI demo provider by default and does not require API keys.

## Run

    cd backend
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

In another terminal:

    cd apps/mobile
    npm install
    npm run start

The default API URL is http://localhost:8000. For a physical device, set
EXPO_PUBLIC_API_URL to the computer's LAN address, for example
http://192.168.1.20:8000.

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
