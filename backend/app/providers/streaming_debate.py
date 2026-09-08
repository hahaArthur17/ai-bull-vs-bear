from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.domain.agents import (
    DebateJudgeRequest,
    DebateJudgeStreamCompleted,
    DebateJudgeStreamDelta,
    DebateJudgeStreamEvent,
    DebateTurnRequest,
    DebateTurnStreamCompleted,
    DebateTurnStreamDelta,
    DebateTurnStreamEvent,
    DebateTurnStreamUsage,
)
from app.providers.debate_agents import DebateJudgeProvider, DebateTurnProvider
from app.providers.deterministic_debate import DeterministicDebateProvider


def preview_text_chunks(content: str, *, max_characters: int = 96) -> tuple[str, ...]:
    """Split buffered text without placing whitespace at frame boundaries."""

    if max_characters < 1:
        raise ValueError("Debate stream chunk size must be positive")
    chunks: list[str] = []
    start = 0
    while start < len(content):
        end = min(start + max_characters, len(content))
        while end < len(content) and (
            content[end].isspace() or content[end - 1].isspace()
        ):
            end += 1
        chunks.append(content[start:end])
        start = end
    return tuple(chunks)


class WholeDraftTurnStreamAdapter:
    """Compatibility stream for a provider that returns one complete draft."""

    def __init__(
        self,
        provider: DebateTurnProvider,
        *,
        max_chunk_characters: int = 96,
    ) -> None:
        if max_chunk_characters < 1 or max_chunk_characters > 1200:
            raise ValueError("Compatibility stream chunk size must be between 1 and 1200")
        self.provider = provider
        self.name = provider.name
        self.version = f"{provider.version}-whole-draft-stream"
        self.max_chunk_characters = max_chunk_characters

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        draft = await asyncio.to_thread(self.provider.generate_turn, request)
        for chunk_index, delta in enumerate(
            preview_text_chunks(
                draft.content,
                max_characters=self.max_chunk_characters,
            ),
            start=1,
        ):
            yield DebateTurnStreamDelta(
                chunk_index=chunk_index,
                delta=delta,
                source="buffered_compatibility",
            )
            await asyncio.sleep(0)
        yield DebateTurnStreamCompleted(
            draft=draft,
            usage=DebateTurnStreamUsage(
                model_name=f"{self.provider.name}:{self.provider.version}",
            ),
        )


class WholeDraftJudgeStreamAdapter:
    """Async compatibility stream for a synchronous Judge provider."""

    def __init__(self, provider: DebateJudgeProvider, *, max_chunk_characters: int = 96) -> None:
        if max_chunk_characters < 1 or max_chunk_characters > 1200:
            raise ValueError("Compatibility stream chunk size must be between 1 and 1200")
        self.provider = provider
        self.name = provider.name
        self.version = f"{provider.version}-whole-draft-stream"
        self.max_chunk_characters = max_chunk_characters

    async def stream_judgement(
        self, request: DebateJudgeRequest
    ) -> AsyncIterator[DebateJudgeStreamEvent]:
        draft = await asyncio.to_thread(self.provider.generate_judgement, request)
        for chunk_index, delta in enumerate(
            preview_text_chunks(draft.summary, max_characters=self.max_chunk_characters), start=1
        ):
            yield DebateJudgeStreamDelta(
                chunk_index=chunk_index, delta=delta, source="buffered_compatibility"
            )
            await asyncio.sleep(0)
        yield DebateJudgeStreamCompleted(
            draft=draft,
            usage=DebateTurnStreamUsage(model_name=f"{self.provider.name}:{self.provider.version}"),
        )


class DeterministicStreamingJudgeProvider(DeterministicDebateProvider):
    """Zero-token Judge stream used unless live Judge generation is explicitly enabled."""

    version = "v2-judge-stream"

    def __init__(self, *, max_chunk_characters: int = 72) -> None:
        if max_chunk_characters < 1 or max_chunk_characters > 1200:
            raise ValueError("Deterministic stream chunk size must be between 1 and 1200")
        self.max_chunk_characters = max_chunk_characters

    async def stream_judgement(
        self, request: DebateJudgeRequest
    ) -> AsyncIterator[DebateJudgeStreamEvent]:
        draft = self.generate_judgement(request)
        for chunk_index, delta in enumerate(
            preview_text_chunks(draft.summary, max_characters=self.max_chunk_characters), start=1
        ):
            yield DebateJudgeStreamDelta(
                chunk_index=chunk_index, delta=delta, source="deterministic"
            )
            await asyncio.sleep(0)
        yield DebateJudgeStreamCompleted(
            draft=draft,
            usage=DebateTurnStreamUsage(model_name=f"{self.name}:{self.version}"),
        )


class DeterministicStreamingDebateProvider(DeterministicDebateProvider):
    """Zero-token async stream used to exercise the real streaming contract."""

    version = "v2-stream"

    def __init__(self, *, max_chunk_characters: int = 72) -> None:
        if max_chunk_characters < 1 or max_chunk_characters > 1200:
            raise ValueError("Deterministic stream chunk size must be between 1 and 1200")
        self.max_chunk_characters = max_chunk_characters

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        draft = self.generate_turn(request)
        for chunk_index, delta in enumerate(
            preview_text_chunks(
                draft.content,
                max_characters=self.max_chunk_characters,
            ),
            start=1,
        ):
            yield DebateTurnStreamDelta(
                chunk_index=chunk_index,
                delta=delta,
                source="deterministic",
            )
            await asyncio.sleep(0)
        yield DebateTurnStreamCompleted(
            draft=draft,
            usage=DebateTurnStreamUsage(
                model_name=f"{self.name}:{self.version}",
            ),
        )
