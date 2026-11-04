import json
from types import SimpleNamespace

import pytest
from app.config import Settings
from app.schemas import MacroContextSnapshot, TechnicalIndicators
from app.services.model_provider import (
    ProviderConfigurationError,
    ProviderError,
    build_analysis_prompt,
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
        build_analysis_provider(Settings(analysis_provider="groq", groq_api_key=None))


def test_groq_analysis_disables_sdk_retries_and_has_an_explicit_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import groq

    options = {}

    def client(**kwargs: object) -> object:
        options.update(kwargs)
        return object()

    monkeypatch.setattr(groq, "Groq", client)
    build_analysis_provider(
        Settings(
            analysis_provider="groq",
            groq_api_key="test-only-key",
            analysis_provider_timeout_seconds=17,
        )
    )
    assert options["timeout"] == 17
    assert options["max_retries"] == 0


@pytest.mark.parametrize("fails", [False, True])
def test_gemini_analysis_bounds_requests_parses_usage_and_redacts_upstream_errors(
    monkeypatch: pytest.MonkeyPatch,
    fails: bool,
) -> None:
    from app.services.analysis import AnalysisService
    from app.services.demo_store import DemoStore
    from google import genai

    options = {}
    captured = {}
    closed = []

    class Model:
        def generate_content(self, **kwargs: object) -> object:
            captured.update(kwargs)
            if fails:
                raise RuntimeError("private provider payload")
            claim = {"text": "Evidence is mixed", "risk_meaning": "New information may change it"}
            return SimpleNamespace(
                text=json.dumps(
                    {
                        "bull": claim,
                        "bear": claim,
                        "judge": {"summary": "Mixed signals", "uncertainty": "Future is unknown"},
                    }
                ),
                usage_metadata=SimpleNamespace(
                    prompt_token_count=10,
                    candidates_token_count=7,
                    total_token_count=17,
                ),
            )

    def client(**kwargs: object) -> object:
        options.update(kwargs)
        return SimpleNamespace(models=Model(), close=lambda: closed.append(True))

    monkeypatch.setattr(genai, "Client", client)
    provider = build_analysis_provider(
        Settings(
            analysis_provider="gemini",
            gemini_api_key="test-only-key",
            gemini_model="test-gemini-flash",
            analysis_provider_timeout_seconds=17,
        )
    )
    indicators = AnalysisService(DemoStore()).create("AAPL").indicators
    if fails:
        with pytest.raises(ProviderError) as error:
            provider.generate("AAPL", "Explain the snapshot", indicators, [], [])
        assert str(error.value) == "Gemini analysis request failed"
    else:
        result = provider.generate("AAPL", "Explain the snapshot", indicators, [], [])
        assert result.draft.judge.summary == "Mixed signals"
        assert result.token_usage.prompt_tokens == 10
        assert result.token_usage.completion_tokens == 7
        assert result.token_usage.total_tokens == 17
    provider.close()
    assert closed == [True]
    assert options["http_options"].timeout == 17000
    assert options["http_options"].retry_options.attempts == 1
    assert captured["model"] == "test-gemini-flash"
    assert captured["config"]["response_mime_type"] == "application/json"


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
