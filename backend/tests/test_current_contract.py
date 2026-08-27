from __future__ import annotations

from typing import Any

import pytest

from app.config import Settings
from app.schemas import TokenUsage
from app.services.analysis import AnalysisService
from app.services.demo_store import DemoStore
from app.services.model_provider import (
    ProviderClaim,
    ProviderDraft,
    ProviderJudge,
    ProviderResult,
)


def test_current_sync_analysis_response_and_snapshot_contract() -> None:
    store = DemoStore()

    response = AnalysisService(store).create("AAPL", user_id="contract-user")
    payload = response.model_dump(mode="json")

    assert set(payload) == {
        "analysis_id",
        "ticker",
        "created_at",
        "question",
        "indicators",
        "snapshot",
        "judge",
        "bull",
        "bear",
        "evidence",
        "disclaimer",
        "guardrail_status",
        "trace",
        "token_usage",
    }
    assert set(payload["snapshot"]) == {
        "retrieved_at",
        "price",
        "retrieved_evidence_count",
        "included_evidence_ids",
        "evidence",
        "macro_context",
        "excluded_external_evidence_count",
        "missing_current_evidence",
    }
    assert payload["snapshot"]["price"]["as_of"] == payload["indicators"]["as_of"]
    assert payload["snapshot"]["included_evidence_ids"] == [
        item["id"] for item in payload["evidence"]
    ]
    assert [step["step"] for step in payload["trace"]] == [
        "technical_agent",
        "news_rag_agent",
        "filing_rag_agent",
        "macro_context_agent",
        "evidence_aggregator",
        "bull_agent",
        "bear_agent",
        "judge_agent",
        "guardrail_agent",
    ]
    assert store.list_analyses("contract-user") == [response]
    assert store.list_analyses("another-user") == []


def test_current_demo_watchlist_contract_is_normalized_sorted_and_user_owned() -> None:
    store = DemoStore()

    assert store.add_watchlist("user-a", "nvda") == ["NVDA"]
    assert store.add_watchlist("user-a", "AAPL") == ["AAPL", "NVDA"]
    assert store.get_watchlist("user-b") == []
    assert store.remove_watchlist("user-a", "nvda") == ["AAPL"]


def test_current_model_provider_boundary_receives_validated_analysis_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class CapturingProvider:
        def generate(
            self,
            ticker: str,
            question: str | None,
            indicators: object,
            evidence: list[object],
            macro_context: list[object],
        ) -> ProviderResult:
            captured.update(
                ticker=ticker,
                question=question,
                indicators=indicators,
                evidence=evidence,
                macro_context=macro_context,
            )
            evidence_id = getattr(evidence[0], "id")
            return ProviderResult(
                draft=ProviderDraft(
                    bull=ProviderClaim(
                        text="Constructive interpretation with uncertainty.",
                        evidence_ids=[evidence_id],
                        signal_strength="weak",
                        confidence="low",
                        risk_meaning="New evidence could change the interpretation.",
                    ),
                    bear=ProviderClaim(
                        text="Material uncertainty remains.",
                        evidence_ids=[evidence_id],
                        signal_strength="weak",
                        confidence="low",
                        risk_meaning="Current risks may outweigh the observed signal.",
                    ),
                    judge=ProviderJudge(
                        summary="The available evidence is limited and mixed.",
                        evidence_strength="weak",
                        uncertainty="The future outcome is unknown.",
                        risk_level="medium",
                    ),
                ),
                token_usage=TokenUsage(
                    model_name="capturing-provider",
                    prompt_tokens=10,
                    completion_tokens=20,
                    total_tokens=30,
                ),
            )

    monkeypatch.setattr(
        "app.services.analysis.build_analysis_provider",
        lambda settings: CapturingProvider(),
    )
    service = AnalysisService(DemoStore(), Settings(analysis_provider="capture"))

    response = service.create("aapl", question="What context is available?")

    assert captured["ticker"] == "AAPL"
    assert captured["question"] == "What context is available?"
    assert captured["indicators"] == response.indicators
    assert [item.id for item in captured["evidence"]] == response.snapshot.included_evidence_ids
    assert captured["macro_context"] == response.snapshot.macro_context
    assert response.token_usage.model_name == "capturing-provider"

