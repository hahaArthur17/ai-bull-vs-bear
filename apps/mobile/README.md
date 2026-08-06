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

Watchlist -> Stock detail -> Technical indicators -> Evidence board ->
Bull vs Bear analysis -> Claim cross-examination.

The mobile app intentionally presents analysis as educational context and
always shows the financial-advice disclaimer.
