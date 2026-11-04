from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.config import Settings, get_settings
from app.schemas import (
    AnalysisResponse,
    AnalysisSnapshot,
    Claim,
    EvidenceItem,
    EvidenceSnapshot,
    ExaminationResponse,
    JudgeSummary,
    MacroContextSnapshot,
    MacroObservation,
    MacroSeries,
    PriceSnapshot,
    TechnicalIndicators,
    TokenUsage,
    TraceStep,
)
from app.services.analysis_evidence import SelectedAnalysisEvidence, select_analysis_evidence
from app.services.demo_store import DemoStore
from app.services.guardrails import DISCLAIMER, apply_guardrails
from app.services.indicators import calculate_indicators
from app.services.model_provider import ProviderClaim, ProviderResult, build_analysis_provider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedAnalysis:
    """Provider-independent claims and usage, ready for a single persisted response."""

    bull: Claim
    bear: Claim
    judge: JudgeSummary
    guardrail_status: str
    token_usage: TokenUsage


class AnalysisService:
    def __init__(self, store: DemoStore, settings: Settings | None = None) -> None:
        self.store = store
        self.settings = settings or get_settings()

    @staticmethod
    def _claim_from_provider(
        agent: str,
        claim: ProviderClaim,
        valid_evidence_ids: set[str],
    ) -> tuple[Claim, bool]:
        # BB-003: a real document ID does not repair an unsupported statement.
        # Discard the generated assertion if any cited ID is unknown or absent.
        # Even accepted IDs establish source membership, not semantic entailment.
        if not claim.evidence_ids or not set(claim.evidence_ids) <= valid_evidence_ids:
            return Claim(
                id=f"{agent}-{uuid4().hex[:8]}",
                agent=agent,
                text=f"The {agent.title()} interpretation could not be grounded in the supplied evidence.",
                evidence_ids=[],
                signal_strength="weak",
                confidence="low",
                risk_meaning="The generated argument was withheld because its source citations could not be verified.",
                terms=[],
            ), True
        evidence_ids = list(dict.fromkeys(claim.evidence_ids))
        safe_text, text_status, _ = apply_guardrails(claim.text)
        safe_risk, risk_status, _ = apply_guardrails(claim.risk_meaning)
        return (
            Claim(
                id=f"{agent}-{uuid4().hex[:8]}",
                agent=agent,  # type: ignore[arg-type]
                text=safe_text.replace(f"\n\n{DISCLAIMER}", ""),
                evidence_ids=evidence_ids,
                signal_strength=claim.signal_strength,  # type: ignore[arg-type]
                confidence=claim.confidence,  # type: ignore[arg-type]
                risk_meaning=safe_risk.replace(f"\n\n{DISCLAIMER}", ""),
                terms=claim.terms[:8],
            ),
            text_status == "rewritten" or risk_status == "rewritten",
        )

    def _macro_context_for_close(self, close_date: str) -> list[MacroContextSnapshot]:
        """Return only observations known on or before the analysed close."""

        try:
            snapshots: list[MacroContextSnapshot] = []
            for raw_series in self.store.get_macro_series():
                series = MacroSeries.model_validate(raw_series)
                candidates = [
                    MacroObservation.model_validate(row)
                    for row in self.store.get_macro_observations(series.code, limit=10)
                    if str(row.get("observation_date", "")) <= close_date
                ]
                if not candidates:
                    continue
                latest = max(candidates, key=lambda item: item.observation_date)
                snapshots.append(
                    MacroContextSnapshot(
                        code=series.code,
                        name=series.name,
                        source=series.source,
                        unit=series.unit,
                        observation_date=latest.observation_date,
                        value=latest.value,
                        retrieved_at=latest.retrieved_at,
                    )
                )
            return snapshots
        except (RuntimeError, ValueError, TypeError, KeyError):
            # Macro background is optional. A cache read problem must not block
            # a date-bound company-evidence analysis.
            return []

    @staticmethod
    def _macro_context_note(macro_context: list[MacroContextSnapshot]) -> str:
        """Describe cached macro context without presenting it as causation."""

        if not macro_context:
            return "No cached market-background observation was available for this close."
        labels = ", ".join(f"{item.name} ({item.observation_date})" for item in macro_context)
        return (
            f"The dated market background includes {labels}. It provides broad context only; "
            "it is not claim evidence and does not establish why this stock moved."
        )

    def create(
        self,
        ticker: str,
        question: str | None = None,
        user_id: str = "demo-user",
        access_token: str | None = None,
    ) -> AnalysisResponse:
        """Freeze the inputs, generate grounded claims, then persist one complete result."""
        normalized = ticker.upper()
        if self.store.get_stock(normalized) is None:
            raise ValueError(f"Unsupported ticker: {normalized}")
        prices = self.store.get_prices(normalized)
        if not prices:
            raise ValueError(f"No cached price history is available for {normalized}")
        indicators = TechnicalIndicators.model_validate(calculate_indicators(normalized, prices))
        latest_price = prices[-1]
        price_as_of = str(latest_price["date"])
        macro_context = self._macro_context_for_close(price_as_of)
        analysis_question = question or (
            f"What available evidence may relate to the {normalized} close on {price_as_of}? "
            "Distinguish contemporaneous context from proven causation."
        )
        selected = select_analysis_evidence(self.store, normalized, analysis_question)
        generated = self._generate(
            normalized, analysis_question, indicators, selected, macro_context
        )
        created_at = datetime.now(timezone.utc).isoformat()
        response = AnalysisResponse(
            analysis_id=str(uuid4()),
            ticker=normalized,
            created_at=created_at,
            question=analysis_question,
            indicators=indicators,
            snapshot=self._build_snapshot(latest_price, created_at, selected, macro_context),
            judge=generated.judge,
            bull=generated.bull,
            bear=generated.bear,
            evidence=selected.items,
            disclaimer=DISCLAIMER,
            guardrail_status=generated.guardrail_status,
            trace=self._build_trace(selected, macro_context),
            token_usage=generated.token_usage,
        )
        self.store.save_analysis(user_id, response.analysis_id, response, access_token)
        return response

    def _generate(
        self,
        ticker: str,
        analysis_question: str,
        indicators: TechnicalIndicators,
        selected: SelectedAnalysisEvidence,
        macro_context: list[MacroContextSnapshot],
    ) -> GeneratedAnalysis:
        """Use the configured provider without changing the grounding contract."""
        has_current_news = "news" in selected.external_types
        if self.settings.analysis_provider.lower().strip() == "demo":
            return self._generate_demo(
                ticker,
                indicators.as_of,
                indicators,
                self._macro_context_note(macro_context),
                has_current_news,
                selected.fallback_ids("bull"),
                selected.fallback_ids("bear"),
            )
        evidence = selected.items
        valid_evidence_ids = {item.id for item in evidence}
        provider_result = self._request_provider(
            ticker,
            analysis_question,
            indicators,
            evidence,
            macro_context,
        )
        bull, bull_rewritten = self._claim_from_provider(
            "bull", provider_result.draft.bull, valid_evidence_ids
        )
        bear, bear_rewritten = self._claim_from_provider(
            "bear", provider_result.draft.bear, valid_evidence_ids
        )
        safe_summary, summary_status, _ = apply_guardrails(provider_result.draft.judge.summary)
        safe_uncertainty, uncertainty_status, _ = apply_guardrails(
            provider_result.draft.judge.uncertainty
        )
        judge = JudgeSummary(
            summary=safe_summary.replace(f"\n\n{DISCLAIMER}", ""),
            evidence_strength=provider_result.draft.judge.evidence_strength,  # type: ignore[arg-type]
            uncertainty=safe_uncertainty.replace(f"\n\n{DISCLAIMER}", ""),
            risk_level=provider_result.draft.judge.risk_level,  # type: ignore[arg-type]
        )
        if not bull.evidence_ids or not bear.evidence_ids:
            # The synthesis must not repeat a claim we just withheld.
            judge = judge.model_copy(
                update={
                    "summary": "Some generated arguments lacked verifiable source citations and were withheld.",
                    "evidence_strength": "weak",
                    "uncertainty": "The remaining evidence does not support a complete comparison of both interpretations.",
                }
            )
        if not has_current_news:
            bull = bull.model_copy(update={"signal_strength": "weak", "confidence": "low"})
            bear = bear.model_copy(update={"signal_strength": "weak", "confidence": "low"})
            judge = judge.model_copy(
                update={
                    "evidence_strength": "weak",
                    "uncertainty": (
                        "No current company news was available for this run; any filing is long-horizon context. "
                        f"{judge.uncertainty}"
                    ),
                }
            )
        guardrail_status = (
            "rewritten"
            if "rewritten" in {summary_status, uncertainty_status}
            or bull_rewritten
            or bear_rewritten
            else "passed"
        )
        token_usage = provider_result.token_usage
        return GeneratedAnalysis(bull, bear, judge, guardrail_status, token_usage)

    def _request_provider(
        self,
        ticker: str,
        question: str,
        indicators: TechnicalIndicators,
        evidence: list[EvidenceItem],
        macro_context: list[MacroContextSnapshot],
    ) -> ProviderResult:
        """Release request-owned connections on both successful and failed generation."""
        provider = build_analysis_provider(self.settings)
        try:
            return provider.generate(ticker, question, indicators, evidence, macro_context)
        finally:
            close = getattr(provider, "close", None)
            if callable(close):
                try:
                    close()
                except Exception as exc:
                    # Cleanup must not hide the original generation failure.
                    logger.warning(
                        "Analysis provider cleanup failed (error_type=%s)", type(exc).__name__
                    )

    @staticmethod
    def _generate_demo(
        ticker: str,
        price_as_of: str,
        indicators: TechnicalIndicators,
        macro_context_note: str,
        has_current_news: bool,
        fallback_bull: list[str],
        fallback_bear: list[str],
    ) -> GeneratedAnalysis:
        """Produce a credential-free example with explicit evidence limitations."""
        bull = Claim(
            id=f"bull-{uuid4().hex[:8]}",
            agent="bull",
            text=(
                f"{ticker} shows a possible constructive momentum pattern based on price position and supporting context. "
                f"{macro_context_note}"
            ),
            evidence_ids=fallback_bull,
            signal_strength="medium" if has_current_news else "weak",
            confidence="medium" if has_current_news else "low",
            risk_meaning="Momentum may continue, but volatility and new information could change the interpretation.",
            terms=["momentum", "moving average"],
        )
        bear = Claim(
            id=f"bear-{uuid4().hex[:8]}",
            agent="bear",
            text=(
                f"{ticker} remains exposed to uncertainty from volatility, competition, and company-specific risks. "
                f"{macro_context_note}"
            ),
            evidence_ids=fallback_bear,
            signal_strength="medium" if has_current_news else "weak",
            confidence="medium" if has_current_news else "low",
            risk_meaning="A negative update or a change in market conditions could outweigh the current technical pattern.",
            terms=["volatility", "risk"],
        )
        raw_summary = (
            f"Evidence available around the {ticker} close on {price_as_of} is mixed: "
            f"technical signals are {indicators.signal_summary.lower()} while the evidence set "
            "includes both supportive context and material risks."
        )
        safe_summary, guardrail_status, _ = apply_guardrails(raw_summary)
        judge = JudgeSummary(
            summary=safe_summary.replace(f"\n\n{DISCLAIMER}", ""),
            evidence_strength="medium" if has_current_news else "weak",
            uncertainty=(
                "No current company news was available for this run; any filing is long-horizon context, "
                "so the result is limited to technical observations and does not establish a daily-move cause or future price outcome."
                if not has_current_news
                else (
                    "The available evidence provides context around the recorded close; "
                    "it does not prove why the price moved or establish a future outcome."
                )
            ),
            risk_level="medium",
        )
        token_usage = TokenUsage(
            model_name="demo-deterministic", prompt_tokens=0, completion_tokens=0, total_tokens=0
        )
        return GeneratedAnalysis(bull, bear, judge, guardrail_status, token_usage)

    @staticmethod
    def _build_snapshot(
        latest_price: dict[str, object],
        created_at: str,
        selected: SelectedAnalysisEvidence,
        macro_context: list[MacroContextSnapshot],
    ) -> AnalysisSnapshot:
        evidence = selected.items
        price_source = str(latest_price.get("source", "demo_fallback"))
        return AnalysisSnapshot(
            retrieved_at=created_at,
            price=PriceSnapshot(
                as_of=str(latest_price["date"]),
                close=float(latest_price["close"]),
                source=(
                    price_source
                    if price_source in {"daily_market_cache", "review_fixture"}
                    else "demo_fallback"
                ),
                is_stale=bool(latest_price.get("is_stale", price_source != "daily_market_cache")),
            ),
            retrieved_evidence_count=selected.retrieved_count,
            included_evidence_ids=[item.id for item in evidence],
            evidence=[
                EvidenceSnapshot(
                    id=item.id,
                    source_type=item.source_type,
                    published_at=item.published_at,
                    freshness=item.freshness,
                )
                for item in evidence
            ],
            macro_context=macro_context,
            excluded_external_evidence_count=selected.excluded_stale_count,
            missing_current_evidence=[
                source_type
                for source_type in ("news", "filing")
                if source_type not in selected.external_types
            ],
        )

    @staticmethod
    def _build_trace(
        selected: SelectedAnalysisEvidence,
        macro_context: list[MacroContextSnapshot],
    ) -> list[TraceStep]:
        """Record the same pipeline stages for deterministic and live providers."""
        return [
            TraceStep(
                step="technical_agent",
                status="completed",
                detail="Calculated RSI, MACD, moving averages, volatility, and volume spike.",
            ),
            TraceStep(
                step="news_rag_agent",
                status="completed",
                detail="Retrieved evidence with source metadata and freshness status.",
            ),
            TraceStep(
                step="filing_rag_agent",
                status="completed",
                detail="Retrieved filing context with source metadata and freshness status.",
            ),
            TraceStep(
                step="macro_context_agent",
                status="completed",
                detail=(
                    f"Attached {len(macro_context)} cached market-background observation(s) dated on or before the close."
                    if macro_context
                    else "No cached market-background observation was available for this close."
                ),
            ),
            TraceStep(
                step="evidence_aggregator",
                status="completed",
                detail=(
                    f"Excluded {selected.excluded_stale_count} stale or undated external document(s) from Debate input."
                    if selected.excluded_stale_count
                    else (
                        f"Added {selected.supplemented_count} source-coverage document(s) to the relevant retrieval."
                        if selected.supplemented_count
                        else "Combined only current external context with technical observations."
                    )
                ),
            ),
            TraceStep(
                step="bull_agent",
                status="completed",
                detail="Generated a positive claim linked to evidence IDs.",
            ),
            TraceStep(
                step="bear_agent",
                status="completed",
                detail="Generated a risk claim linked to evidence IDs.",
            ),
            TraceStep(
                step="judge_agent",
                status="completed",
                detail="Produced a neutral synthesis with uncertainty and risk level.",
            ),
            TraceStep(
                step="guardrail_agent",
                status="completed",
                detail="Checked response language against the financial-advice policy.",
            ),
        ]

    def get(
        self,
        analysis_id: str,
        user_id: str = "demo-user",
        access_token: str | None = None,
    ) -> AnalysisResponse | None:
        value = self.store.get_analysis(user_id, analysis_id, access_token)
        return value if isinstance(value, AnalysisResponse) else None

    def examine(
        self,
        claim_id: str,
        question_type: str,
        user_id: str = "demo-user",
        access_token: str | None = None,
    ) -> ExaminationResponse:
        analysis = self.store.find_analysis_by_claim(user_id, claim_id, access_token)
        if not isinstance(analysis, AnalysisResponse):
            raise KeyError(f"Unknown claim: {claim_id}")
        claim = (
            analysis.bull
            if analysis.bull.id == claim_id
            else analysis.bear
            if analysis.bear.id == claim_id
            else None
        )
        if claim is None:
            raise KeyError(f"Unknown claim: {claim_id}")
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
