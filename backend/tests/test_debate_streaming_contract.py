from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.agents import (
    DebateTurnDraft,
    DebateTurnRequest,
    DebateTurnStreamCompleted,
    DebateTurnStreamDelta,
    DebateTurnStreamEvent,
    DebateTurnStreamUsage,
)
from app.domain.factors import FactorSnapshot
from app.providers.debate_agents import DebateStreamingTurnProvider
from app.services.analysis_context import build_analysis_context
from app.services.debate_streaming import (
    DebateTurnStreamError,
    collect_debate_turn_stream,
)


SESSION_ID = UUID("00000000-0000-4000-8000-000000000501")
BRANCH_ID = UUID("00000000-0000-4000-8000-000000000502")
GENERATION_ID = UUID("00000000-0000-4000-8000-000000000503")


def build_request(*, max_output_chars: int = 300) -> DebateTurnRequest:
    context = build_analysis_context("AAPL", as_of="2026-08-28")
    return DebateTurnRequest(
        session_id=SESSION_ID,
        branch_id=BRANCH_ID,
        generation_id=GENERATION_ID,
        ticker="AAPL",
        role="bull",
        round_number=1,
        exchange_number=1,
        analysis_context=context,
        factor_snapshot=FactorSnapshot(ticker="AAPL", as_of=context.as_of),
        max_output_chars=max_output_chars,
    )


def build_draft(content: str = "A bounded streamed argument.") -> DebateTurnDraft:
    return DebateTurnDraft(
        content=content,
        confidence="low",
        signal_strength="weak",
        risk_meaning="New evidence may change the interpretation.",
    )


def usage() -> DebateTurnStreamUsage:
    return DebateTurnStreamUsage(
        model_name="test-model",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )


class SequenceStreamingProvider:
    name = "sequence-stream"
    version = "test-v1"

    def __init__(self, events: list[DebateTurnStreamEvent]) -> None:
        self.events = events

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        for event in self.events:
            await asyncio.sleep(0)
            yield event


def collect(provider: DebateStreamingTurnProvider, request: DebateTurnRequest | None = None):
    return asyncio.run(collect_debate_turn_stream(provider, request or build_request()))


def test_stream_delta_preserves_boundary_whitespace_exactly() -> None:
    delta = DebateTurnStreamDelta(
        chunk_index=1,
        delta=" leading and trailing ",
        source="live_provider",
    )

    assert delta.delta == " leading and trailing "


def test_stream_usage_requires_consistent_token_totals() -> None:
    with pytest.raises(ValidationError, match="prompt plus completion"):
        DebateTurnStreamUsage(
            model_name="test-model",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=20,
        )


def test_valid_stream_is_structural_and_collects_only_after_completion() -> None:
    draft = build_draft()
    provider = SequenceStreamingProvider(
        [
            DebateTurnStreamDelta(
                chunk_index=1,
                delta="A bounded ",
                source="live_provider",
            ),
            DebateTurnStreamDelta(
                chunk_index=2,
                delta="streamed argument.",
                source="live_provider",
            ),
            DebateTurnStreamCompleted(draft=draft, usage=usage()),
        ]
    )

    result = collect(provider)

    assert isinstance(provider, DebateStreamingTurnProvider)
    assert result.draft == draft
    assert result.delta_count == 2
    assert result.usage.total_tokens == 15


@pytest.mark.parametrize(
    ("events", "message"),
    [
        (
            [
                DebateTurnStreamDelta(
                    chunk_index=2,
                    delta="out of order",
                    source="live_provider",
                )
            ],
            "not contiguous",
        ),
        (
            [
                DebateTurnStreamDelta(
                    chunk_index=1,
                    delta="missing completion",
                    source="live_provider",
                )
            ],
            "without a completion",
        ),
        (
            [
                DebateTurnStreamDelta(
                    chunk_index=1,
                    delta="different text",
                    source="live_provider",
                ),
                DebateTurnStreamCompleted(draft=build_draft(), usage=usage()),
            ],
            "does not match",
        ),
        (
            [
                DebateTurnStreamDelta(
                    chunk_index=1,
                    delta="A bounded streamed argument.",
                    source="live_provider",
                ),
                DebateTurnStreamCompleted(
                    draft=build_draft(),
                    finish_reason="length",
                    usage=usage(),
                ),
            ],
            "did not finish normally",
        ),
        (
            [
                DebateTurnStreamDelta(
                    chunk_index=1,
                    delta="A bounded streamed argument.",
                    source="live_provider",
                ),
                DebateTurnStreamCompleted(draft=build_draft(), usage=usage()),
                DebateTurnStreamDelta(
                    chunk_index=2,
                    delta="late data",
                    source="live_provider",
                ),
            ],
            "after completion",
        ),
    ],
)
def test_invalid_stream_cannot_become_a_complete_turn(
    events: list[DebateTurnStreamEvent],
    message: str,
) -> None:
    with pytest.raises(DebateTurnStreamError, match=message):
        collect(SequenceStreamingProvider(events))


def test_stream_enforces_request_output_bound() -> None:
    content = "x" * 301
    provider = SequenceStreamingProvider(
        [
            DebateTurnStreamDelta(
                chunk_index=1,
                delta=content,
                source="live_provider",
            ),
            DebateTurnStreamCompleted(draft=build_draft(content), usage=usage()),
        ]
    )

    with pytest.raises(DebateTurnStreamError, match="output bound"):
        collect(provider, build_request(max_output_chars=300))


def test_private_provider_failure_is_wrapped_in_a_safe_stream_error() -> None:
    class FailingProvider:
        name = "failing-stream"
        version = "test-v1"

        async def stream_turn(
            self,
            request: DebateTurnRequest,
        ) -> AsyncIterator[DebateTurnStreamEvent]:
            raise RuntimeError("private upstream response")
            yield  # pragma: no cover

    with pytest.raises(DebateTurnStreamError) as error:
        collect(FailingProvider())

    assert str(error.value) == "Turn provider stream failed"
    assert "private upstream response" not in str(error.value)
