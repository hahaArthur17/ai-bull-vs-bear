"""Batch streamed text and publish only after its recoverable prefix is durable."""

import asyncio
from collections.abc import Callable

from app.domain.agents import DebateJudgeStreamDelta, DebateTurnStreamDelta
from app.domain.debate import DebateDraftCheckpoint
from app.repositories.debate_repository import DebateUnitOfWork

DURABLE_DELTA_BATCH_MAX_CHARACTERS = 240
DURABLE_DELTA_BATCH_MAX_CHUNKS = 12


class DurableDeltaBatch:
    """Bound database writes while retaining the entire cumulative prefix."""

    def __init__(self) -> None:
        self.content = ""
        self.pending = ""
        self.pending_chunks = 0
        self.source: str | None = None
        self.emitted_count = 0

    def append(self, delta: str, source: str) -> None:
        if self.source is not None and self.source != source:
            raise ValueError("Durable delta batch cannot mix provider sources")
        self.content += delta
        self.pending += delta
        self.pending_chunks += 1
        self.source = source

    @property
    def ready(self) -> bool:
        return (
            len(self.pending) >= DURABLE_DELTA_BATCH_MAX_CHARACTERS
            or self.pending_chunks >= DURABLE_DELTA_BATCH_MAX_CHUNKS
        )

    def take(self) -> tuple[int, str, str, str] | None:
        if not self.pending or self.source is None:
            return None
        self.emitted_count += 1
        result = (self.emitted_count, self.pending, self.source, self.content)
        self.pending = ""
        self.pending_chunks = 0
        self.source = None
        return result


class DraftDeltaPublisher:
    """Share the ordering contract between Bull/Bear and Judge streams.

    A Stop can race a checkpoint write. Recheck generation ownership *after*
    that write and before publishing, so a cancelled generation cannot reveal
    another fragment. Checkpoint failures propagate to the worker retry policy.
    """

    def __init__(
        self,
        *,
        repository: DebateUnitOfWork,
        checkpoint: DebateDraftCheckpoint,
        durable: bool,
        assert_active: Callable[[], None],
        emit: Callable[[int, str, str], None],
    ) -> None:
        self.repository = repository
        self.checkpoint = checkpoint
        self.durable = durable
        self.assert_active = assert_active
        self.emit = emit
        self.batch = DurableDeltaBatch()

    async def publish(self, event: DebateTurnStreamDelta | DebateJudgeStreamDelta) -> None:
        if not self.durable:
            await asyncio.to_thread(self.assert_active)
            self.emit(event.chunk_index, event.delta, event.source)
            return
        if self.batch.pending and self.batch.source != event.source:
            await self.flush()
        self.batch.append(event.delta, event.source)
        if self.batch.ready:
            await self.flush()

    async def flush(self) -> None:
        batch = self.batch.take()
        if batch is None:
            return
        index, delta, source, content = batch
        checkpoint = self.checkpoint.model_copy(update={"content": content})
        await asyncio.to_thread(self.repository.checkpoint_draft, checkpoint)
        await asyncio.to_thread(self.assert_active)
        self.emit(index, delta, source)
