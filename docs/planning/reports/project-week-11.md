# Project Week 11 Report

Period: 2026-08-28

Status: Phase 4 live-provider and client boundaries complete; integration and
cancellation pending

## Goal

Implement one genuine asynchronous model stream and one authenticated mobile
consumer without spending external quota, exposing raw structured output, or
claiming that the current synchronous preview is already live.

## Completed work

- Revalidated Groq and Gemini official documentation before selecting the
  first provider. Groq was chosen because the repository already uses its
  server-side key/configuration and exposes an async Chat Completions stream.
- Replaced the retired `llama-3.3-70b-versatile` default with the current
  `openai/gpt-oss-20b` model, updated the SDK floor, and added an independent
  `DEBATE_STREAMING_PROVIDER=deterministic` safe default (`77c33c4`).
- Added `GroqStreamingDebateProvider` and a selection factory (`a6529c3`). The
  provider streams plain user-facing prose because Groq Structured Outputs and
  streaming are not currently compatible. Server code owns evidence aliases,
  citations, rebuttal targets, confidence/signal metadata, risk meaning, and
  term extraction.
- Added bounded context/prompt construction, output limits, hidden-reasoning
  exclusion, zero automatic retries, cross-chunk financial phrase detection,
  normal-finish checks, exact content reconstruction, safe upstream errors, and
  required frozen-evidence citations.
- Added a latest-sequence response header to expired-cursor `409` responses so
  canonical reload can reconnect without looping on the same expired cursor
  (`b1ba884`).
- Added `DebateStreamClient`, an authenticated XHR SSE transport, incremental
  frame parser, canonical/draft reducer, generation filtering, ordered delta
  checks, canonical completion replacement, cursor recovery, and a small API
  factory for future screen integration (`7057628`).

## Verification

```shell
PYTHONPATH=backend backend/.venv/bin/python -m pytest backend/tests -q
(cd apps/mobile && npm run typecheck)
(cd apps/mobile && npm run test:stream)
(cd apps/mobile && npm run build:web)
```

Result on 2026-08-28: 233 backend tests and 5 mobile stream tests passed. Expo
Web export and the mobile TypeScript check passed. The only backend warning is
the existing Starlette/httpx test-client deprecation.

All Groq behavior was tested with an injected fake async client. No Groq or
Gemini API request was sent, no model tokens were consumed, no hosted migration
was applied, and production configuration remains deterministic and V2-off.

## Free-tier fit reviewed

Groq's published base Free Plan limits for `openai/gpt-oss-20b` on the review
date are 30 requests/minute, 1,000 requests/day, 8,000 tokens/minute, and
200,000 tokens/day. One complete current design uses ten live Bull/Bear Turn
requests across both rounds; Judge generation remains a separate provider
boundary. The request-count ceiling alone would therefore be 100 complete
two-round demos per day, but prompt/output token limits, other app traffic, and
failed attempts will reduce that number. This supports a bounded classroom and
portfolio demo, not an unrestricted public launch. The future Worker should
start with concurrency one or two and treat `429` as visible backpressure.

Current limits must be rechecked in the account dashboard before a live demo;
they are organization-level and may differ from the public base table.

## Decisions

- Model output is plain text, not a streamed JSON object. Partial JSON is a poor
  user experience and cannot use Groq Structured Outputs concurrently with
  streaming at this time.
- Public prompts use `[E1]` aliases rather than internal evidence IDs. The
  server maps and validates aliases only at completion.
- Provider deltas are temporary UI state. Only a validated `turn.completed`
  message is canonical and may enter history or a later agent prompt.
- `DEBATE_STREAMING_PROVIDER` is independent of `ANALYSIS_PROVIDER` and
  `DEBATE_WORKFLOW_V2`; enabling one feature cannot silently spend six live
  Turn requests.

## Honest capability boundary

The current `POST /debates` remains a synchronous deterministic preview and
returns the Session only after Round 1 has completed. Therefore the new client
cannot yet display generation while that request runs and is intentionally not
mounted in `App.tsx`. The process-local SSE broker is not a durable Queue or a
cross-instance event log. Native-device XHR streaming also still needs a real
iOS/Android smoke test.

## Recommended next tasks

1. Implement cancellation generation checks so late provider completion cannot
   persist after a user interrupts a Debate.
2. Add Supabase Queue/Worker start semantics so the API can return the Session
   before generation and the client can attach immediately.
3. Mount the stream client in an extracted Debate screen only after the queued
   start contract exists; retain canonical reload as the fallback.

## Related documents

- [`API contract`](../../api/api-contract.md)
- [`agent workflow`](../../agents/agent-workflow.md)
- [`architecture overview`](../../architecture/overview.md)
- [`current status`](../current-status.md)
- [`portfolio implementation plan`](../portfolio-implementation-plan.md)

## Official references reviewed

- [Groq streaming and async completions](https://console.groq.com/docs/text-chat)
- [Groq model deprecations](https://console.groq.com/docs/deprecations)
- [Groq Free Plan rate limits](https://console.groq.com/docs/rate-limits)
- [Groq Structured Outputs compatibility](https://console.groq.com/docs/structured-outputs)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
