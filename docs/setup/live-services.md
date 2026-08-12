# Live Services Setup

This document records the non-secret configuration needed to move AI Bull vs
Bear from deterministic demo mode to real services.

Never commit `.env`, API keys, database passwords, service-role keys, access
tokens, or screenshots that display credentials.

## Local environment file

Create `.env` at the repository root from `.env.example`. The application reads
these variables when the backend starts.

```dotenv
ENVIRONMENT=development
ANALYSIS_PROVIDER=groq
CORS_ORIGINS=http://localhost:8081,http://localhost:19006

SUPABASE_URL=
SUPABASE_ANON_KEY=

GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
```

Only one model provider needs to be active. Keep unused provider keys empty.

## Groq

Console: <https://console.groq.com/keys>

1. Create a key for the current Groq project with a descriptive name such as
   `ai-bull-vs-bear-local`.
2. Copy it once and place it in `GROQ_API_KEY` in the local `.env` file.
3. Set `ANALYSIS_PROVIDER=groq`.
4. Restart the backend and run one analysis request.
5. Confirm that `token_usage.model_name` contains the configured Groq model.

## Gemini

Console: <https://aistudio.google.com/api-keys>

Gemini is an alternative model provider. Create and configure a Gemini key only
when it will be used; the app does not require both Groq and Gemini at once.

1. Create or select a Google Cloud project dedicated to this application.
2. Create an API key and restrict it to the relevant Gemini/Generative Language
   API where supported.
3. Place the value in `GEMINI_API_KEY` and set
   `ANALYSIS_PROVIDER=gemini`.
4. Restart the backend and verify a real analysis response.

## Supabase

Dashboard: <https://supabase.com/dashboard>

1. Create a dedicated project named `AI Bull vs Bear`; do not reuse an
   unrelated production project.
2. Open SQL Editor and run `backend/supabase/schema.sql`.
3. Enable the required sign-in method under Authentication.
4. Copy the project URL and publishable/anon key into `SUPABASE_URL` and
   `SUPABASE_ANON_KEY`.
5. Keep the service-role key server-side only. It must never be bundled into the
   Expo application.
6. Verify row-level security with two separate test users before relying on the
   project for persisted user data.

## Verification checklist

- [x] `.env` exists locally and remains ignored by Git.
- [x] One real model provider is selected.
- [x] The selected model provider completes an analysis successfully.
- [x] The API response contains real token usage and no secret values.
- [x] The Supabase schema has been applied to the dedicated project.
- [ ] Authentication works for a test user.
- [ ] Watchlist and analysis history survive a backend restart.
- [ ] Row-level security prevents one user from reading another user's data.

## Current live configuration

Last verified: 2026-08-12

- Groq is the selected local provider, and a real structured analysis completed
  successfully with provider token usage.
- The dedicated Supabase project is running in the Asia-Pacific region.
- The repository schema created ten public tables and explicit minimum Data API
  grants. An unauthenticated read of the empty `stocks` table returned HTTP 200.
- Supabase Auth and application persistence are still implementation work; the
  presence of URL/key configuration does not mean the DemoStore has been
  replaced.
- The initially generated database password was exposed during setup and must
  be rotated in the Supabase Database Settings page before direct Postgres
  connections are used.

## Rotation and incident response

If a credential is exposed in chat, logs, screenshots, or Git history, revoke
it immediately in the provider console and create a replacement. Removing a
secret from the current file is not enough once it has entered Git history.
