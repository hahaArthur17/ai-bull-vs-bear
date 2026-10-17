# Multi-Agent Workflow

Last reviewed: 2026-10-17.

Both the legacy single-response workflow and the default-off stateful V2
workflow are implemented. Production flags and completed acceptance are tracked
in [current status](../planning/current-status.md), separately from code.
Bull, Bear, Judge and Explainer are roles with distinct prompts/context and may
use the same underlying model; they are not independently trained models.

## Legacy analysis

`POST /analysis/{ticker}` builds technical/evidence context and returns one
validated Bull/Bear/Judge JSON response. Bull and Bear do not see or rebut each
other's text on this path. The service retrieves/ranks technical, news and
filing evidence, validates provider output, filters unknown evidence IDs,
records token usage and applies financial-language guardrails. Fixed claim
examination remains available through `/claims/{claim_id}/examine`.

`ANALYSIS_PROVIDER=demo` is deterministic; Groq and Gemini are explicit optional
legacy providers. This choice does not select V2 streaming providers.

## Stateful V2

### 1. Freeze the input

The Factor Registry validates technical, market-quote, macro, news/filing and
structured financial-fact adapters. One immutable Session snapshot preserves
completed-close prices/indicators, dated evidence, macro observations,
normalized factors, missing categories, allowed evidence IDs and the initial
question. Current-data admission checks apply before live provider work.
Later refreshes and continuation do not silently replace that snapshot.

### 2. Admit Round 1

With Queue enabled, Session/Job/identifier-only Queue creation is atomic and
idempotent; the API returns `202 Accepted`. A bounded lifespan Worker claims
and executes the stage. Queue-disabled preview runs deterministically in the
request, returns `201`, and labels chunks `buffered_compatibility`.

### 3. Stream three exchanges

The default Bull opening produces Bull → Bear → Bull → Bear → Bull → Bear;
`opening_side=bear` reverses the side order. Each rebuttal targets the latest
opponent message and receives a bounded projection of the prior transcript.
The async provider streams prose, while citations and metadata remain validated
on the server. Live Turn selection is independent and defaults to deterministic.

Completion requires contiguous/matching text, normal finish, output bounds,
valid rebuttal target and in-snapshot evidence IDs. Grounded source-quote checks
reject unsupported attribution; guardrails reject/rewrite disallowed financial
language. Only a valid complete Turn and its citations are atomically persisted.
Transport failure does not turn partial text into a complete claim.

### 4. Interim Judge and pause

The independently configured Judge summarizes agreements, disagreements,
evidence strength, missing inputs and uncertainty, then the Session becomes
`awaiting_user`. Queued Judges have their own streamed `judge.delta` events and
usage records; enabling live Turns does not enable live Judges.

### 5. Explain or explicitly challenge

Explanation uses one owned active-branch message, an exact selected passage
and only its linked evidence. It returns a read-only panel without appending a
message, creating a Job, rotating generation or changing Session state. It has
its own provider and admission window. Complete messages and eligible
non-empty frozen interrupted prefixes can be explained; partial content is not
promoted to evidence.

At the Interim pause, an explicit Round 2 Challenge requires a selected complete
message/passage and question. The API atomically persists the intervention and
User message and enqueues Round 2. The UI keeps read-only inquiry and explicit
Round 2 submission separate. General message branching is deferred.

### 6. Round 2 and Final Judge

Four alternating Turns address the Challenge, followed by the Final Judge. The
canonical Session becomes `completed`, and History can reopen its durable
messages, citations and final summary. A completed Session cannot be continued
as another Round 2.

## Resumable Stop and terminal Cancel

With `DEBATE_INTERRUPTIONS_ENABLED=true`, Stop can freeze the exact displayed
prefix or act before first output. The repository validates the prefix against
checkpoint/canonical content, rotates generation, removes later transcript
material and enters `interrupted_awaiting_user`. The retained prefix is explicitly
incomplete; no late completion can overwrite it.

The user can request read-only Explanation, save an interjection, explicitly
Continue or End. Saving a point does not dispatch a model. Continue requires
that point and atomically creates a new generation/Job, retaining the original
snapshot and bounded remaining role plan. End settles cancellation. Terminal
Cancel is separate and does not invite continuation.

Provider transport cancellation is best effort. A request already dispatched
can consume tokens even if its output is later discarded. Client reveal pacing
is also separate from provider admission: it does not guarantee that the next
role's request waits for the current bubble to finish displaying.

## Recovery and accounting

Queue retry/redelivery resumes from the next missing complete planned Turn;
transactions and uniqueness prevent duplicate canonical writes. Owner-scoped
idempotency locks supplement that database boundary. SSE reconnect resumes from
an ordered cursor; an expired cursor/gap reloads canonical Session/Messages.
The event broker is process-local, so the supported live topology keeps Worker
and API together.

Draft checkpoints and provider attempts are separate records. Attempts retain
admission/dispatch/outcome, provider/model and reported/unknown token usage even
when Stop shortens a previously completed message. The backend audit endpoint
is available with interruptions enabled; V2 mobile token diagnostics are still
a follow-up. Explanation usage is not part of the Debate attempt ledger.

See [API contract](../api/api-contract.md),
[output contracts](claim-output-format.md), and
[guardrail policy](guardrail-policy.md) for the exact boundaries. Automated,
hosted/live and simulator evidence does not certify the pending physical-device
acceptance.
