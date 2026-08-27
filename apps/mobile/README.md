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

The current analysis screen waits for one complete API response. Streamed
multi-turn messages, Queue status, user interventions, and the
financial-technology redesign are planned in the canonical
[`portfolio implementation plan`](../../docs/planning/portfolio-implementation-plan.md).

Shared colours, spacing, radii, and app styles live in `src/theme.ts`; reusable
base UI components live under `src/components/`. Watchlist, History, and About
are standalone screen modules under `src/screens/`. Stock detail, charts,
Debate, Evidence, and Examination remain in `App.tsx` and will be extracted
incrementally with their owning feature phases.

The mobile app intentionally presents analysis as educational context and
always shows the financial-advice disclaimer.
