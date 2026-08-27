# Agent Output Contracts

Last reviewed: 2026-08-27

## Implemented single-response claim

The current provider returns one Bull and one Bear claim in the following
shape, plus a separate Judge object:

```json
{
  "agent": "bull",
  "claims": [
    {
      "id": "bull_claim_1",
      "text": "The stock shows short-term positive momentum based on recent price movement.",
      "evidence_ids": ["technical_001", "news_003"],
      "signal_strength": "medium",
      "confidence": "medium",
      "risk_meaning": "Momentum may continue, but high volatility can increase uncertainty.",
      "terms": ["momentum", "volatility"]
    }
  ]
}
```

## Planned multi-turn message

The portfolio milestone replaces a single claim per side with persisted,
ordered messages. A completed Bull/Bear message contains:

```json
{
  "message_id": "uuid",
  "session_id": "uuid",
  "branch_id": "uuid",
  "generation_id": "uuid",
  "sequence_number": 2,
  "round_number": 1,
  "exchange_number": 1,
  "role": "bear",
  "message_kind": "rebuttal",
  "content": "A cautious rebuttal that addresses the prior Bull point.",
  "rebuttal_target_message_id": "uuid",
  "evidence_ids": ["existing-evidence-id"],
  "signal_strength": "weak",
  "confidence": "low",
  "risk_meaning": "What uncertainty means for this interpretation.",
  "terms": ["volatility"],
  "is_complete": true
}
```

Partial text travels through `turn.delta` events and is not treated as a claim.
Only the complete, guardrailed, citation-filtered message is persisted as the
canonical turn. Full event and persistence contracts live in the
[`portfolio implementation plan`](../planning/portfolio-implementation-plan.md).
