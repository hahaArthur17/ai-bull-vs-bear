import pytest

from app.config import Settings
from app.schemas import MacroContextSnapshot, TechnicalIndicators
from app.services.model_provider import (
    ProviderConfigurationError,
    ProviderError,
    build_analysis_provider,
    build_analysis_prompt,
    parse_provider_payload,
)


def test_parse_provider_payload_accepts_json_code_fence() -> None:
    draft = parse_provider_payload(
        """```json
        {
          "bull": {"text": "Constructive context", "evidence_ids": ["news-1"], "signal_strength": "medium", "confidence": "medium", "risk_meaning": "New information could change it", "terms": ["momentum"]},
          "bear": {"text": "Material risks remain", "evidence_ids": ["filing-1"], "signal_strength": "medium", "confidence": "medium", "risk_meaning": "Risks may outweigh the signal", "terms": ["volatility"]},
          "judge": {"summary": "Evidence is mixed", "evidence_strength": "medium", "uncertainty": "The future is unknown", "risk_level": "medium"}
        }
        ```"""
    )
    assert draft.bull.evidence_ids == ["news-1"]
    assert draft.judge.risk_level == "medium"


def test_parse_provider_payload_rejects_invalid_shape() -> None:
    with pytest.raises(ProviderError):
        parse_provider_payload('{"bull": {"text": "missing fields"}}')


def test_provider_requires_key_when_selected() -> None:
    with pytest.raises(ProviderConfigurationError, match="GROQ_API_KEY"):
        build_analysis_provider(Settings(analysis_provider="groq", groq_api_key=None))


def test_analysis_prompt_labels_macro_context_as_non_causal_background() -> None:
    prompt = build_analysis_prompt(
        "AAPL",
        "What context is available?",
        TechnicalIndicators(
            ticker="AAPL",
            as_of="2026-08-20",
            rsi=50,
            macd=0,
            macd_signal=0,
            moving_average_20=100,
            moving_average_50=99,
            volatility=20,
            volume_spike=False,
            signal_summary="Mixed",
        ),
        [],
        [
            MacroContextSnapshot(
                code="vix",
                name="CBOE Volatility Index",
                source="fred",
                unit="index points",
                observation_date="2026-08-20",
                value=17.25,
                retrieved_at="2026-08-21T00:00:00+00:00",
            )
        ],
    )

    assert '"code": "vix"' in prompt
    assert "not proof of causation" in prompt
    assert "do not let it compensate for missing current company news" in prompt
