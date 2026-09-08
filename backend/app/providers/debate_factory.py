from __future__ import annotations

from typing import Any

from app.config import Settings
from app.providers.debate_agents import DebateStreamingJudgeProvider, DebateStreamingTurnProvider
from app.providers.groq_streaming_judge import GroqStreamingJudgeProvider
from app.providers.groq_streaming_debate import (
    GroqDebateConfigurationError,
    GroqStreamingDebateProvider,
)
from app.providers.streaming_debate import (
    DeterministicStreamingDebateProvider,
    DeterministicStreamingJudgeProvider,
)


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


def build_debate_streaming_judge_provider(
    settings: Settings,
    *,
    groq_client: Any | None = None,
) -> DebateStreamingJudgeProvider:
    """Select Judge streaming independently so Turn opt-in cannot spend Judge quota."""

    selected = settings.debate_streaming_judge_provider.strip().lower()
    if selected == "deterministic":
        return DeterministicStreamingJudgeProvider()
    if selected == "groq":
        return GroqStreamingJudgeProvider(
            api_key=settings.groq_api_key,
            model=settings.debate_judge_groq_model,
            timeout_seconds=settings.debate_provider_timeout_seconds,
            client=groq_client,
        )
    raise GroqDebateConfigurationError(
        "Unsupported DEBATE_STREAMING_JUDGE_PROVIDER. Use deterministic or groq."
    )
