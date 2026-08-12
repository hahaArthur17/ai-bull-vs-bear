import pytest

from app.config import Settings
from app.services.model_provider import (
    ProviderConfigurationError,
    ProviderError,
    build_analysis_provider,
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
        build_analysis_provider(Settings(analysis_provider="groq"))
