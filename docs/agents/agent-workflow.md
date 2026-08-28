# Multi-Agent Workflow

Last reviewed: 2026-08-28

The steps immediately below describe the deployed single-response workflow.
The default-off deterministic multi-turn preview and its remaining target
transport follow it. Development sequencing is canonical in the
[`portfolio implementation plan`](../planning/portfolio-implementation-plan.md).

## Implemented single-response workflow

### Step 1: Technical Agent

Input:
- OHLCV price data

Output:
- RSI
- MACD
- moving averages
- volatility
- volume spike
- technical signal summary

### Step 2: News RAG Agent

Input:
- ticker
- user question
- recent news chunks

Output:
- relevant news evidence
- news summary

### Step 3: Filing RAG Agent

Input:
- ticker
- company filing chunks

Output:
- relevant filing evidence
- risk factor summary

### Step 4: Evidence Aggregator

Input:
- technical signals
- news evidence
- filing evidence

Output:
- structured context for AI agents

### Step 5: Bull Agent

Output:
- positive claims
- evidence IDs
- confidence level

### Step 6: Bear Agent

Output:
- risk claims
- evidence IDs
- confidence level

### Step 7: Judge Agent

Output:
- neutral summary
- evidence strength
- uncertainty
- risk level

### Step 8: Guardrail Agent

Output:
- safe final response
- removed or rewritten unsafe advice

The deployed legacy provider returns Bull, Bear, and Judge in one validated JSON
payload. Bull and Bear do not see or rebut each other's text on that path.

## Target stateful workflow

The database-independent session/message/job/event contracts, deterministic
round plans, state-transition rules, turn/Judge provider inputs, and Phase 3
persistence adapters described below are now implemented. A credential-free
provider/orchestrator also executes both rounds and persists the user Challenge.
Default-off Session, Message, and Challenge API routes now expose that workflow
as `synchronous_preview`. A bounded event broker and authenticated SSE endpoint
also expose ordered buffered preview chunks, citations, Judge events,
heartbeats, and terminal state with resume cursors. A default-off Groq async
Turn adapter and a resumable Web/React Native client now implement the two ends
of the live stream boundary, but the current HTTP creation route and screen do
not select them. Worker/Queue transport, term explanation, mounted live UI, and
cross-process replay remain target behaviour. Generation-scoped cancellation
now exists at the orchestrator, repository, API, event, and mobile reducer
boundaries.

### Step 1: Build one immutable analysis context

The Factor Registry calls current `FactorProvider` adapters for technical,
macro, news, filing, and structured financial-fact inputs. It validates and
freezes one context containing:

- completed-close price and indicator state;
- dated/freshness-tagged evidence;
- dated, non-causal macro context;
- normalized factors and missing categories;
- allowed evidence IDs; and
- the initial user question.

All turns in one branch use the same snapshot. A later data refresh cannot
rewrite an existing Debate.

### Step 2: Queue round one

The API creates a Debate session and stage job, sends the job ID to the durable
Queue, returns `202 Accepted`, and exposes session/job status plus a stream path.
The Queue payload contains identifiers only.

The implemented Phase 3 preview stops before this transport boundary: it
creates the same canonical Session/Job records but executes the deterministic
stage in the request and returns `201 Created` after completion.

### Step 3: Produce three exchanges

The bounded Worker executes:

1. Bull opening.
2. Bear rebuttal.
3. Bull counterargument.
4. Bear counterargument.
5. Bull closing position.
6. Bear closing position.

Every rebuttal receives the complete prior transcript and explicitly targets
the latest opponent message. Every completed message is guardrailed, filtered
to allowed citations, stored, and then exposed as complete to the UI.

The deterministic Phase 3 orchestrator now proves the transcript, latest-target,
citation, persistence, and state-transition parts of this step without Queue or
streaming.

The Phase 4 compatibility path now divides each already completed deterministic
draft into whitespace-safe `buffered_compatibility` deltas and publishes them before
the canonical complete-message event. This proves event ordering and
reconstruction only; it is not described as provider token streaming.

An async Provider contract and orchestrator path are also implemented in code.
They accept contiguous whitespace-preserving deltas as they arrive, require one
normal completion whose full draft exactly matches those deltas, enforce the
Turn output bound and frozen evidence/rebuttal target, and then persist. A
mid-stream failure publishes the safe Session failure but never creates a
complete message for the partial text. The selected HTTP preview still uses the
compatibility path until one live provider and client stream are verified.

### Step 4: Interim Judge and user pause

The Judge summarizes agreements, disagreements, evidence strength, missing
evidence, and uncertainty without choosing a trade. The session moves to
`awaiting_user`.

### Step 5: Explain or challenge

- Explanation Agent: explains a selected term/passage with minimal context and
  does not alter the Debate state.
- User challenge: records a free-form intervention, cancels any current
  generation on a best-effort basis, rejects late chunks by `generation_id`,
  and creates a new branch from the last complete message.

### Step 6: Produce round two

The Queue runs four messages focused on the user's question:

1. Bull answer.
2. Bear rebuttal.
3. Bull counterargument.
4. Bear closing response.

The final Judge summarizes the complete active branch and the session moves to
`completed`.

The deterministic Phase 3 path implements this sequence on the current branch;
the default-off Phase 4 path now implements live provider token streaming and
cancellation generation handling in code, but the synchronous creation route
does not yet make mid-generation intervention reachable from the screen.

### Step 7: Recover and audit

Queue redelivery skips already completed planned turns. Database uniqueness and
Redis idempotency locks prevent duplicate sessions/messages, while token usage,
job attempts, queue wait, duration, and safe failure codes remain observable.

## Agent naming boundary

Bull, Bear, Judge, and Explainer may use one underlying model with distinct
role prompts and transcript context. Describe this accurately as stateful
multi-agent orchestration, not independently trained autonomous models.
