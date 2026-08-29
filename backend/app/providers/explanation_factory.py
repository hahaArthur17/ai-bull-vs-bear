from __future__ import annotations

from app.config import Settings
from app.providers.explanation import (
    DeterministicExplanationProvider,
    ExplanationProvider,
)


class ExplanationProviderConfigurationError(RuntimeError):
    """The selected Explanation provider is not available safely."""


def build_explanation_provider(settings: Settings) -> ExplanationProvider:
    """Select the Explanation provider without coupling it to Debate streaming."""

    selected = settings.explanation_provider.strip().lower()
    if selected == "deterministic":
        return DeterministicExplanationProvider()
    raise ExplanationProviderConfigurationError(
        "Unsupported EXPLANATION_PROVIDER. Use deterministic."
    )
