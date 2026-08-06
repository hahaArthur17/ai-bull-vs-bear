from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import (
    AnalysisResponse,
    Claim,
    ExaminationResponse,
    EvidenceItem,
    JudgeSummary,
    TechnicalIndicators,
    TokenUsage,
    TraceStep,
)
from app.services.demo_store import DemoStore
from app.services.guardrails import DISCLAIMER, apply_guardrails
from app.services.indicators import calculate_indicators


class AnalysisService:
    def __init__(self, store: DemoStore) -> None:
        self.store = store

    def create(self, ticker: str, question: str | None = None) -> AnalysisResponse:
        normalized = ticker.upper()
        stock = self.store.get_stock(normalized)
        if stock is None:
            raise ValueError(f"Unsupported ticker: {normalized}")
        prices = self.store.get_prices(normalized)
        raw_indicators = calculate_indicators(normalized, prices)
        indicators = TechnicalIndicators.model_validate(raw_indicators)
        evidence = [EvidenceItem.model_validate(item) for item in self.store.get_evidence(normalized)]
        technical_id = f"technical-{normalized.lower()}-001"
        bull_evidence = [technical_id, evidence[0].id] if evidence else [technical_id]
        bear_evidence = [f"technical-{normalized.lower()}-004", evidence[-1].id] if evidence else [technical_id]
        bull = Claim(
            id=f"bull-{uuid4().hex[:8]}",
            agent="bull",
            text=f"{normalized} shows a possible constructive momentum pattern based on price position and supporting context.",
            evidence_ids=bull_evidence,
            signal_strength="medium",
            confidence="medium",
            risk_meaning="Momentum may continue, but volatility and new information could change the interpretation.",
            terms=["momentum", "moving average"],
        )
        bear = Claim(
            id=f"bear-{uuid4().hex[:8]}",
            agent="bear",
            text=f"{normalized} remains exposed to uncertainty from volatility, competition, and company-specific risks.",
            evidence_ids=bear_evidence,
            signal_strength="medium",
            confidence="medium",
            risk_meaning="A negative update or a change in market conditions could outweigh the current technical pattern.",
            terms=["volatility", "risk"],
        )
        raw_summary = (
            f"Evidence for {normalized} is mixed: technical signals are {indicators.signal_summary.lower()} "
            "while the evidence set includes both supportive context and material risks."
        )
        safe_summary, guardrail_status, _ = apply_guardrails(raw_summary)
        judge = JudgeSummary(
            summary=safe_summary.replace(f"\n\n{DISCLAIMER}", ""),
            evidence_strength="medium",
            uncertainty="The demo evidence is cached and does not establish a future price outcome.",
            risk_level="medium",
        )
        analysis_id = f"analysis-{uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()
        trace = [
            TraceStep(step="technical_agent", status="completed", detail="Calculated RSI, MACD, moving averages, volatility, and volume spike."),
            TraceStep(step="news_rag_agent", status="completed", detail="Retrieved cached news evidence with source metadata."),
            TraceStep(step="filing_rag_agent", status="completed", detail="Retrieved cached filing risk evidence with source metadata."),
            TraceStep(step="evidence_aggregator", status="completed", detail="Combined technical, news, and filing context."),
            TraceStep(step="bull_agent", status="completed", detail="Generated a positive claim linked to evidence IDs."),
            TraceStep(step="bear_agent", status="completed", detail="Generated a risk claim linked to evidence IDs."),
            TraceStep(step="judge_agent", status="completed", detail="Produced a neutral synthesis with uncertainty and risk level."),
            TraceStep(step="guardrail_agent", status="completed", detail="Checked response language against the financial-advice policy."),
        ]
        token_usage = TokenUsage(model_name="demo-deterministic", prompt_tokens=0, completion_tokens=0, total_tokens=0)
        response = AnalysisResponse(
            analysis_id=analysis_id,
            ticker=normalized,
            created_at=created_at,
            question=question,
            indicators=indicators,
            judge=judge,
            bull=bull,
            bear=bear,
            evidence=evidence,
            disclaimer=DISCLAIMER,
            guardrail_status=guardrail_status,
            trace=trace,
            token_usage=token_usage,
        )
        self.store.save_analysis(analysis_id, response)
        return response

    def get(self, analysis_id: str) -> AnalysisResponse | None:
        value = self.store.get_analysis(analysis_id)
        return value if isinstance(value, AnalysisResponse) else None

    def examine(self, claim_id: str, question_type: str) -> ExaminationResponse:
        for analysis in self.store.list_analyses():
            if not isinstance(analysis, AnalysisResponse):
                continue
            claim = analysis.bull if analysis.bull.id == claim_id else analysis.bear if analysis.bear.id == claim_id else None
            if claim is None:
                continue
            evidence = [item for item in analysis.evidence if item.id in claim.evidence_ids]
            if question_type == "explain_term":
                answer = f"{', '.join(claim.terms)} are descriptive terms used to interpret the available evidence; they are not a prediction."
            elif question_type == "evidence_support":
                answer = f"This claim is linked to {', '.join(claim.evidence_ids)}. The sources add context but do not guarantee that the claim will remain true."
            elif question_type == "signal_strength":
                answer = f"The signal is {claim.signal_strength} with {claim.confidence} confidence because the evidence is limited and uncertainty remains."
            else:
                answer = claim.risk_meaning
            return ExaminationResponse(
                claim_id=claim_id,
                question_type=question_type,  # type: ignore[arg-type]
                answer=answer,
                evidence=evidence,
                disclaimer=DISCLAIMER,
            )
        raise KeyError(f"Unknown claim: {claim_id}")

