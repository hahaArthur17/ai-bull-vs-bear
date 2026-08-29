from __future__ import annotations

from typing import Any

from app.config import Settings
from app.providers.explanation import (
    DeterministicExplanationProvider,
    ExplanationProvider,
)
from app.providers.groq_explanation import (
    GroqExplanationConfigurationError,
    GroqExplanationProvider,
)


class ExplanationProviderConfigurationError(RuntimeError):
    """The selected Explanation provider is not available safely."""


def build_explanation_provider(
    settings: Settings,
    *,
    groq_client: Any | None = None,
) -> ExplanationProvider:
    """Select the Explanation provider without coupling it to Debate streaming."""

    selected = settings.explanation_provider.strip().lower()
    if selected == "deterministic":
        return DeterministicExplanationProvider()
    if selected == "groq":
        try:
            return GroqExplanationProvider(
                api_key=settings.groq_api_key,
                model=settings.explanation_groq_model,
                timeout_seconds=settings.explanation_provider_timeout_seconds,
                max_completion_tokens=settings.explanation_max_completion_tokens,
                client=groq_client,
            )
        except GroqExplanationConfigurationError as exc:
            raise ExplanationProviderConfigurationError(str(exc)) from exc
    raise ExplanationProviderConfigurationError(
        "Unsupported EXPLANATION_PROVIDER. Use deterministic or groq."
    )
