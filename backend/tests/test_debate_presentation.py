from __future__ import annotations

from app.domain.debate import DebateMessage, DebateMessageEvidence
from app.services.debate_presentation import (
    build_debate_message_presentation,
    safe_source_destination,
)
from test_current_factor_providers import build_current_context
from test_debate_domain import BRANCH_ID, GENERATION_ID, NOW, SESSION_ID


def _message(**updates: object) -> DebateMessage:
    return DebateMessage.model_validate(
        {
            "id": "00000000-0000-4000-8000-000000000091",
            "session_id": SESSION_ID,
            "branch_id": BRANCH_ID,
            "generation_id": GENERATION_ID,
            "sequence_number": 1,
            "round_number": 1,
            "exchange_number": 1,
            "role": "bull",
            "message_kind": "argument",
            "content": "A bounded argument based on dated evidence.",
            "metadata": {
                "interpretation": "The Bull reads the snapshot as supportive context.",
                "risk_meaning": "New evidence could change this interpretation.",
            },
            "created_at": NOW,
            **updates,
        }
    )


def test_presentation_uses_only_persisted_citations_and_the_frozen_context() -> None:
    context = build_current_context()
    message = _message()
    citations = (
        DebateMessageEvidence(
            message_id=message.id,
            evidence_id="filing-aapl-1",
            citation_order=2,
            support_span="A persisted, bounded filing span.",
        ),
        DebateMessageEvidence(
            message_id=message.id,
            evidence_id="news-aapl-1",
            citation_order=1,
            support_span="A persisted, bounded news span.",
        ),
    )

    presentation = build_debate_message_presentation(message, citations, context)

    assert presentation.argument == message.content
    assert presentation.interpretation == message.metadata["interpretation"]
    assert presentation.uncertainty == message.metadata["risk_meaning"]
    assert [fact.evidence_id for fact in presentation.facts_used] == [
        "news-aapl-1",
        "filing-aapl-1",
    ]
    assert presentation.facts_used[0].source is None
    assert presentation.facts_used[0].fact == "A dated announcement with company context."
    assert "source" in presentation.facts_used[0].missing_metadata
    assert presentation.facts_used[0].source_destination == "https://example.com/news"
    assert presentation.facts_used[0].support_span == "A persisted, bounded news span."
    assert presentation.facts_used[0].freshness.status == "current"


def test_presentation_marks_old_or_unknown_citation_details_explicitly_missing() -> None:
    context = build_current_context()
    message = _message(metadata={"uncertainty": "The retained record has no newer context."})
    citation = DebateMessageEvidence(
        message_id=message.id,
        evidence_id="removed-evidence-id",
        citation_order=1,
    )

    presentation = build_debate_message_presentation(message, (citation,), context)
    fact = presentation.facts_used[0]

    assert presentation.interpretation is None
    assert presentation.uncertainty == "The retained record has no newer context."
    assert fact.evidence_id == "removed-evidence-id"
    assert fact.support_span is None
    assert set(fact.missing_metadata) == {
        "evidence_type",
        "title",
        "fact",
        "source",
        "date",
        "support_span",
        "source_destination",
    }


def test_safe_source_destination_rejects_non_https_or_credentialed_urls() -> None:
    assert safe_source_destination("https://example.com/evidence") == "https://example.com/evidence"
    for unsafe in (
        None,
        "http://example.com/evidence",
        "https://user:pass@example.com/evidence",
        "https://user@example.com/evidence",
        "https://example.com /evidence",
        "https://localhost/evidence",
        "https://research.internal/evidence",
        "https://127.0.0.1/evidence",
        "https://10.0.0.4/evidence",
        "https://[::1]/evidence",
        "javascript:alert(1)",
        "/relative/evidence",
    ):
        assert safe_source_destination(unsafe) is None
