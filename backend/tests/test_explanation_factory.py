import pytest

from app.config import Settings
from app.providers.explanation import DeterministicExplanationProvider
from app.providers.explanation_factory import (
    ExplanationProviderConfigurationError,
    build_explanation_provider,
)


def test_explanation_provider_defaults_to_credential_free_deterministic_mode() -> None:
    provider = build_explanation_provider(Settings())

    assert isinstance(provider, DeterministicExplanationProvider)


def test_explanation_provider_rejects_unknown_selection_safely() -> None:
    with pytest.raises(ExplanationProviderConfigurationError, match="EXPLANATION_PROVIDER"):
        build_explanation_provider(Settings(explanation_provider="unknown"))
