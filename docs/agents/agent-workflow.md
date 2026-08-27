# Multi-Agent Workflow

Last reviewed: 2026-08-27

The steps immediately below describe the implemented single-response workflow.
The stateful multi-turn target follows it. Development sequencing is canonical
in the
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

The implemented provider returns Bull, Bear, and Judge in one validated JSON
payload. Bull and Bear do not yet see or rebut each other's text.

## Target stateful workflow

The database-independent session/message/job/event contracts, deterministic
round plans, state-transition rules, turn/Judge provider inputs, and Phase 3
persistence adapters described below are now implemented. A credential-free
provider/orchestrator also executes both rounds and persists the user Challenge.
Feature-flagged API routes, Worker/Queue transport, live-provider generation,
and streaming remain target behaviour for later steps.

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
live token streaming and cancellation generation handling remain Phase 4.

### Step 7: Recover and audit

Queue redelivery skips already completed planned turns. Database uniqueness and
Redis idempotency locks prevent duplicate sessions/messages, while token usage,
job attempts, queue wait, duration, and safe failure codes remain observable.

## Agent naming boundary

Bull, Bear, Judge, and Explainer may use one underlying model with distinct
role prompts and transcript context. Describe this accurately as stateful
multi-agent orchestration, not independently trained autonomous models.
