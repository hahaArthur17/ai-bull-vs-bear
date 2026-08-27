from __future__ import annotations

from typing import Any

from app.config import Settings
from app.providers.debate_agents import DebateStreamingTurnProvider
from app.providers.groq_streaming_debate import (
    GroqDebateConfigurationError,
    GroqStreamingDebateProvider,
)
from app.providers.streaming_debate import DeterministicStreamingDebateProvider


def build_debate_streaming_turn_provider(
    settings: Settings,
    *,
    groq_client: Any | None = None,
) -> DebateStreamingTurnProvider:
    """Select an async Turn provider without coupling it to the analysis provider."""

    selected = settings.debate_streaming_provider.strip().lower()
    if selected == "deterministic":
        return DeterministicStreamingDebateProvider()
    if selected == "groq":
        return GroqStreamingDebateProvider(
            api_key=settings.groq_api_key,
            model=settings.debate_groq_model,
            timeout_seconds=settings.debate_provider_timeout_seconds,
            client=groq_client,
        )
    raise GroqDebateConfigurationError(
        "Unsupported DEBATE_STREAMING_PROVIDER. Use deterministic or groq."
    )
