from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.config import Settings
from app.schemas import EvidenceItem, TechnicalIndicators, TokenUsage


class ProviderError(RuntimeError):
    """Raised when a configured model provider cannot complete an analysis."""


class ProviderConfigurationError(ProviderError):
    """Raised when a provider is selected but its local configuration is missing."""


from pydantic import BaseModel, Field, ValidationError


class ProviderClaim(BaseModel):
    text: str = Field(min_length=1, max_length=1200)
    evidence_ids: list[str] = Field(default_factory=list)
    signal_strength: Literal["weak", "medium", "strong"] = "medium"
    confidence: Literal["low", "medium", "high"] = "medium"
    risk_meaning: str = Field(min_length=1, max_length=1200)
    terms: list[str] = Field(default_factory=list)


class ProviderJudge(BaseModel):
    summary: str = Field(min_length=1, max_length=1600)
    evidence_strength: Literal["weak", "medium", "strong"] = "medium"
    uncertainty: str = Field(min_length=1, max_length=1200)
    risk_level: Literal["low", "medium", "high"] = "medium"


class ProviderDraft(BaseModel):
    bull: ProviderClaim
    bear: ProviderClaim
    judge: ProviderJudge


@dataclass(frozen=True)
class ProviderResult:
    draft: ProviderDraft
    token_usage: TokenUsage


class AnalysisModelProvider(Protocol):
    def generate(
        self,
        ticker: str,
        question: str | None,
        indicators: TechnicalIndicators,
        evidence: list[EvidenceItem],
    ) -> ProviderResult:
        ...


def build_analysis_prompt(
    ticker: str,
    question: str | None,
    indicators: TechnicalIndicators,
    evidence: list[EvidenceItem],
) -> str:
    evidence_lines = [
        json.dumps(
            {
                "id": item.id,
                "source_type": item.source_type,
                "title": item.title,
                "published_at": item.published_at,
                "excerpt": item.excerpt,
            },
            ensure_ascii=False,
        )
        for item in evidence
    ]
    evidence_block = "\n".join(evidence_lines) or "(no evidence returned)"
    question_text = question or "Explain the available signals and uncertainty."
    return f"""You are the analysis layer of an educational stock-evidence application.
Do not give buy, sell, hold, price-target, or guaranteed-return advice. Explain
possible interpretations, cite only the evidence IDs supplied below, and make
uncertainty explicit.

Ticker: {ticker}
User question: {question_text}
Technical indicators:
{indicators.model_dump_json()}

Evidence items (do not invent IDs):
{evidence_block}

Return JSON only, with exactly this shape:
{{
  "bull": {{
    "text": "a cautious constructive interpretation",
    "evidence_ids": ["existing evidence id"],
    "signal_strength": "weak|medium|strong",
    "confidence": "low|medium|high",
    "risk_meaning": "what could invalidate this interpretation",
    "terms": ["short explanatory terms"]
  }},
  "bear": {{
    "text": "a cautious risk interpretation",
    "evidence_ids": ["existing evidence id"],
    "signal_strength": "weak|medium|strong",
    "confidence": "low|medium|high",
    "risk_meaning": "what the risk means for interpretation",
    "terms": ["short explanatory terms"]
  }},
  "judge": {{
    "summary": "neutral synthesis without a trading recommendation",
    "evidence_strength": "weak|medium|strong",
    "uncertainty": "what remains unknown",
    "risk_level": "low|medium|high"
  }}
}}
"""


def parse_provider_payload(raw_text: str) -> ProviderDraft:
    """Parse JSON from a provider while tolerating a Markdown code fence."""

    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        payload: Any = json.loads(text)
        return ProviderDraft.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ProviderError("The model returned an invalid analysis JSON payload.") from exc


def _usage_from_response(response: Any, model_name: str) -> TokenUsage:
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    return TokenUsage(
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


class GroqAnalysisProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.groq_api_key:
            raise ProviderConfigurationError(
                "GROQ_API_KEY is missing. Add it to the local .env file or use ANALYSIS_PROVIDER=demo."
            )
        try:
            from groq import Groq
        except ImportError as exc:
            raise ProviderConfigurationError(
                "The Groq package is not installed. Run pip install -r backend/requirements.txt."
            ) from exc
        self.model = settings.groq_model
        self.client = Groq(api_key=settings.groq_api_key)

    def generate(
        self,
        ticker: str,
        question: str | None,
        indicators: TechnicalIndicators,
        evidence: list[EvidenceItem],
    ) -> ProviderResult:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Return valid JSON only. Follow the requested schema exactly.",
                    },
                    {
                        "role": "user",
                        "content": build_analysis_prompt(ticker, question, indicators, evidence),
                    },
                ],
                temperature=0.2,
                max_tokens=1200,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if not content:
                raise ProviderError("Groq returned an empty analysis response.")
            draft = parse_provider_payload(content)
            return ProviderResult(draft=draft, token_usage=_usage_from_response(response, self.model))
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Groq analysis request failed: {exc}") from exc


class GeminiAnalysisProvider:
    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is missing. Add it to the local .env file or use ANALYSIS_PROVIDER=demo."
            )
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ProviderConfigurationError(
                "The Gemini package is not installed. Run pip install -r backend/requirements.txt."
            ) from exc
        genai.configure(api_key=settings.gemini_api_key)
        self.model_name = settings.gemini_model
        self.model = genai.GenerativeModel(self.model_name)

    def generate(
        self,
        ticker: str,
        question: str | None,
        indicators: TechnicalIndicators,
        evidence: list[EvidenceItem],
    ) -> ProviderResult:
        try:
            response = self.model.generate_content(
                build_analysis_prompt(ticker, question, indicators, evidence),
                generation_config={
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                },
            )
            content = getattr(response, "text", None)
            if not content:
                raise ProviderError("Gemini returned an empty analysis response.")
            draft = parse_provider_payload(content)
            usage = getattr(response, "usage_metadata", None)
            prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
            completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
            total_tokens = int(getattr(usage, "total_token_count", prompt_tokens + completion_tokens) or 0)
            return ProviderResult(
                draft=draft,
                token_usage=TokenUsage(
                    model_name=self.model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                ),
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Gemini analysis request failed: {exc}") from exc


def build_analysis_provider(settings: Settings) -> AnalysisModelProvider:
    provider = settings.analysis_provider.lower().strip()
    if provider == "groq":
        return GroqAnalysisProvider(settings)
    if provider == "gemini":
        return GeminiAnalysisProvider(settings)
    raise ProviderConfigurationError(
        f"Unsupported ANALYSIS_PROVIDER={settings.analysis_provider!r}. Use demo, groq, or gemini."
    )
