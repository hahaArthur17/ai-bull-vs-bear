from __future__ import annotations

import asyncio
from threading import get_ident

from app.domain.agents import DebateTurnDraft
from app.providers.debate_agents import DebateStreamingTurnProvider, DebateTurnProvider
from app.providers.streaming_debate import (
    DeterministicStreamingDebateProvider,
    WholeDraftTurnStreamAdapter,
    preview_text_chunks,
)
from app.services.debate_streaming import collect_debate_turn_stream
from test_debate_streaming_contract import build_request


class ThreadRecordingProvider:
    name = "whole-draft-test"
    version = "v1"

    def __init__(self, content: str) -> None:
        self.content = content
        self.thread_id: int | None = None

    def generate_turn(self, request):
        self.thread_id = get_ident()
        return DebateTurnDraft(
            content=self.content,
            confidence="low",
            signal_strength="weak",
            risk_meaning="New evidence may change the interpretation.",
        )


def test_preview_chunks_round_trip_without_boundary_whitespace_loss() -> None:
    content = "x" * 95 + "   " + "y" * 100 + "\n" + "final text"

    chunks = preview_text_chunks(content, max_characters=96)

    assert "".join(chunks) == content
    assert all(chunk == chunk.strip() for chunk in chunks)


def test_whole_draft_adapter_runs_blocking_provider_off_event_loop_thread() -> None:
    calling_thread = get_ident()
    provider = ThreadRecordingProvider("A complete compatibility argument.")
    adapter = WholeDraftTurnStreamAdapter(provider, max_chunk_characters=10)

    result = asyncio.run(collect_debate_turn_stream(adapter, build_request()))

    assert isinstance(provider, DebateTurnProvider)
    assert isinstance(adapter, DebateStreamingTurnProvider)
    assert provider.thread_id is not None
    assert provider.thread_id != calling_thread
    assert result.draft.content == provider.content
    assert result.delta_count > 1
    assert result.usage.total_tokens == 0


def test_deterministic_provider_implements_sync_and_true_async_contracts() -> None:
    provider = DeterministicStreamingDebateProvider(max_chunk_characters=24)

    async def collect_events():
        return [event async for event in provider.stream_turn(build_request())]

    events = asyncio.run(collect_events())
    result = asyncio.run(collect_debate_turn_stream(provider, build_request()))

    assert isinstance(provider, DebateTurnProvider)
    assert isinstance(provider, DebateStreamingTurnProvider)
    assert all(event.source == "deterministic" for event in events[:-1])
    assert events[-1].kind == "completed"
    assert "".join(event.delta for event in events[:-1]) == result.draft.content
