# Agent Output Contracts

Last reviewed: 2026-10-17

## Implemented single-response claim

The legacy provider returns one Bull and one Bear claim in the following
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

## Implemented V2 message record

The separately enabled V2 workflow persists ordered messages. API detail wraps
each one as `{ "message": ..., "citations": [...], "presentation": ... }`.
A completed Bull/Bear message contains:

```json
{
  "id": "uuid",
  "session_id": "uuid",
  "branch_id": "uuid",
  "generation_id": "uuid",
  "sequence_number": 2,
  "round_number": 1,
  "exchange_number": 1,
  "role": "bear",
  "message_kind": "rebuttal",
  "content": "A cautious rebuttal that addresses the prior Bull point.",
  "metadata": {
    "responds_to_message_id": "uuid"
  },
  "signal_strength": "weak",
  "confidence": "low",
  "terms": ["volatility"],
  "is_complete": true,
  "cancelled_at": null,
  "created_at": "2026-10-17T00:00:00Z"
}
```

This is an illustrative message, not a provider response schema. Citations are
separate `DebateMessageEvidence` records (`message_id`, `evidence_id`, order and
optional support span), not a top-level `evidence_ids` field on the message.
The optional server-authored presentation contains `argument`, `facts_used`,
`interpretation` and `uncertainty` from the frozen snapshot and message metadata.

Partial text travels through `turn.delta` / `judge.delta` and durable draft
checkpoints; it is not a complete claim. Validated complete output is persisted
atomically with citations. Explicit Stop can retain a canonical **incomplete**
prefix with `is_complete=false`, `cancelled_at`, and interruption metadata;
it must not be presented as a validated complete Turn. Provider attempts retain
usage independently of that shortened transcript. See the
[API contract](../api/api-contract.md) and
[domain models](../../backend/app/domain/debate.py) for authoritative fields.
