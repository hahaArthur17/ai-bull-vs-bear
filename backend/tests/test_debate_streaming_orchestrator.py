from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import math
from uuid import UUID

import pytest

from app.domain.agents import (
    DebateJudgeRequest,
    DebateJudgeStreamCompleted,
    DebateJudgeStreamEvent,
    DebateTurnRequest,
    DebateTurnStreamCompleted,
    DebateTurnStreamDelta,
    DebateTurnStreamEvent,
    DebateTurnStreamUsage,
)
from app.domain.debate import DebateDraftCheckpoint, DebateMessage
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.providers.streaming_debate import (
    DeterministicStreamingDebateProvider,
    DeterministicStreamingJudgeProvider,
    preview_text_chunks,
)
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_event_broker import InMemoryDebateEventBroker
from app.services.debate_orchestrator import (
    DURABLE_DELTA_BATCH_MAX_CHUNKS,
    DebateOrchestrationError,
    DebateOrchestrator,
    DebateRetryableOrchestrationError,
)
from test_debate_orchestrator import StepClock, build_queued_round_one


class TokenRecordingStreamProvider(DeterministicStreamingDebateProvider):
    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        async for event in super().stream_turn(request):
            if event.kind == "completed":
                yield DebateTurnStreamCompleted(
                    draft=event.draft,
                    usage=DebateTurnStreamUsage(
                        model_name="token-stream-test",
                        prompt_tokens=3,
                        completion_tokens=2,
                        total_tokens=5,
                    ),
                )
            else:
                yield event


class TokenRecordingJudgeProvider(DeterministicStreamingJudgeProvider):
    async def stream_judgement(
        self,
        request: DebateJudgeRequest,
    ) -> AsyncIterator[DebateJudgeStreamEvent]:
        async for event in super().stream_judgement(request):
            if event.kind == "completed":
                yield DebateJudgeStreamCompleted(
                    draft=event.draft,
                    usage=DebateTurnStreamUsage(
                        model_name="judge-token-stream-test",
                        prompt_tokens=7,
                        completion_tokens=4,
                        total_tokens=11,
                    ),
                )
            else:
                yield event


class RecordingProviderPacer:
    def __init__(self) -> None:
        self.calls = 0

    async def wait(self) -> None:
        self.calls += 1


class InterruptingStreamProvider:
    name = "interrupting-stream"
    version = "test-v1"

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        yield DebateTurnStreamDelta(
            chunk_index=1,
            delta="A partial private-provider turn ",
            source="live_provider",
        )
        raise RuntimeError("private upstream disconnect payload")


class RetryableStreamProvider:
    name = "retryable-stream"
    version = "test-v1"

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        error = RuntimeError("private rate-limit response")
        error.retryable = True  # type: ignore[attr-defined]
        error.retry_after_seconds = 4  # type: ignore[attr-defined]
        raise error
        yield  # pragma: no cover


class RetryOnceAfterTwoTurnsProvider(DeterministicStreamingDebateProvider):
    def __init__(self) -> None:
        super().__init__(max_chunk_characters=32)
        self.request_count = 0
        self.failed_once = False

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        self.request_count += 1
        if self.request_count == 3 and not self.failed_once:
            self.failed_once = True
            error = RuntimeError("private temporary disconnect")
            error.retryable = True  # type: ignore[attr-defined]
            error.retry_after_seconds = 4  # type: ignore[attr-defined]
            raise error
        async for event in super().stream_turn(request):
            yield event


class CancellationBoundaryStreamProvider(DeterministicStreamingDebateProvider):
    def __init__(
        self,
        *,
        pause_after_chunks: int = DURABLE_DELTA_BATCH_MAX_CHUNKS,
    ) -> None:
        # Pause exactly when twelve small provider fragments reach the durable
        # batching chunk bound and become one user-visible checkpoint.
        super().__init__(max_chunk_characters=1)
        self.pause_after_chunks = pause_after_chunks
        self.first_delta_sent = asyncio.Event()
        self.release_late_output = asyncio.Event()

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        delta_count = 0
        async for event in super().stream_turn(request):
            yield event
            if event.kind == "delta":
                delta_count += 1
            if delta_count == self.pause_after_chunks:
                self.first_delta_sent.set()
                await self.release_late_output.wait()


class CancellationBoundaryJudgeProvider(DeterministicStreamingJudgeProvider):
    def __init__(self) -> None:
        super().__init__(max_chunk_characters=16)
        self.first_delta_sent = asyncio.Event()
        self.release_late_output = asyncio.Event()
        self.stream_closed = asyncio.Event()

    async def stream_judgement(
        self,
        request: DebateJudgeRequest,
    ) -> AsyncIterator[DebateJudgeStreamEvent]:
        first_delta = True
        try:
            async for event in super().stream_judgement(request):
                yield event
                if first_delta and event.kind == "delta":
                    first_delta = False
                    self.first_delta_sent.set()
                    await self.release_late_output.wait()
        finally:
            self.stream_closed.set()


class CheckpointRecordingRepository(InMemoryDebateRepository):
    def __init__(self, operation_log: list[tuple[str, UUID, str]]) -> None:
        super().__init__()
        self.operation_log = operation_log

    def checkpoint_draft(
        self,
        message: DebateDraftCheckpoint | DebateMessage,
    ) -> None:
        super().checkpoint_draft(message)
        message_id = message.id if isinstance(message, DebateMessage) else message.message_id
        self.operation_log.append(("checkpoint", message_id, message.content))


class CheckpointOrderBroker(InMemoryDebateEventBroker):
    def __init__(self, operation_log: list[tuple[str, UUID, str]]) -> None:
        super().__init__(max_events_per_session=4096)
        self.operation_log = operation_log

    def publish(self, session_id, event_type, *, payload=None, timestamp=None):
        event = super().publish(
            session_id,
            event_type,
            payload=payload,
            timestamp=timestamp,
        )
        if event_type in {"turn.delta", "judge.delta"}:
            assert payload is not None
            self.operation_log.append(
                ("event", UUID(str(payload["message_id"])), str(payload["delta"]))
            )
        return event


def test_async_orchestrator_streams_then_persists_complete_messages_and_usage() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    provider = TokenRecordingStreamProvider(max_chunk_characters=32)
    judge_provider = TokenRecordingJudgeProvider(max_chunk_characters=32)
    broker = InMemoryDebateEventBroker()
    pacer = RecordingProviderPacer()
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        streaming_turn_provider=provider,
        streaming_judge_provider=judge_provider,
        event_publisher=broker,
        clock=StepClock(),
        provider_request_pacer=pacer,
    )

    session = asyncio.run(orchestrator.execute_job_streaming(job.id))
    messages = repository.list_messages(
        session.id,
        session.user_id,
        branch_id=session.active_branch_id,
    )
    events = broker.replay(session.id)
    stored_job = repository.get_job(job.id)

    assert session.status == "awaiting_user"
    assert pacer.calls == 7
    assert len(messages) == 7
    assert all(message.is_complete for message in messages)
    assert all(
        message.metadata.get("stream_mode") == "async_provider"
        for message in messages
        if message.role in {"bull", "bear"}
    )
    assert sum(event.type == "turn.completed" for event in events) == 6
    assert any(event.type == "judge.delta" for event in events)
    assert messages[-1].metadata["stream_mode"] == "async_provider"
    assert messages[-1].metadata["usage"]["total_tokens"] == 11
    assert messages[-1].metadata["model_name"] == "judge-token-stream-test"
    assert messages[-1].metadata["provider"] == judge_provider.name
    assert all(
        event.payload["source"] == "deterministic"
        for event in events
        if event.type == "turn.delta"
    )
    first_turn_events = [
        event
        for event in events
        if event.type == "turn.delta"
        and event.payload["message_id"] == str(messages[0].id)
    ]
    assert [event.payload["delta_index"] for event in first_turn_events] == list(
        range(1, len(first_turn_events) + 1)
    )
    assert [event.payload["delta"] for event in first_turn_events] == list(
        preview_text_chunks(messages[0].content, max_characters=32)
    )
    assert events[-1].payload["execution_mode"] == "async_stream"
    assert stored_job is not None
    assert stored_job.provider_request_count == 7
    assert stored_job.prompt_tokens == 25
    assert stored_job.completion_tokens == 16
    assert stored_job.total_tokens == 41

    event_count = len(events)
    assert asyncio.run(orchestrator.execute_job_streaming(job.id)) == session
    assert len(broker.replay(session.id)) == event_count


def test_checkpointed_stream_batches_only_durable_contiguous_deltas() -> None:
    operation_log: list[tuple[str, UUID, str]] = []
    repository = CheckpointRecordingRepository(operation_log)
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    provider = DeterministicStreamingDebateProvider(max_chunk_characters=1)
    judge_provider = DeterministicStreamingJudgeProvider(max_chunk_characters=1)
    broker = CheckpointOrderBroker(operation_log)
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        streaming_turn_provider=provider,
        streaming_judge_provider=judge_provider,
        checkpoint_drafts=True,
        event_publisher=broker,
        clock=StepClock(),
    )

    session = asyncio.run(orchestrator.execute_job_streaming(job.id))
    messages = repository.list_messages(
        session.id,
        session.user_id,
        branch_id=session.active_branch_id,
    )
    delta_events = [
        event
        for event in broker.replay(session.id)
        if event.type in {"turn.delta", "judge.delta"}
    ]

    assert len(operation_log) == len(delta_events) * 2
    visible_by_message: dict[UUID, str] = {}
    for checkpoint, emitted in zip(operation_log[::2], operation_log[1::2], strict=True):
        assert checkpoint[0] == "checkpoint"
        assert emitted[0] == "event"
        assert checkpoint[1] == emitted[1]
        previous = visible_by_message.get(emitted[1], "")
        assert checkpoint[2] == previous + emitted[2]
        visible_by_message[emitted[1]] = checkpoint[2]

    for message in messages:
        matching_events = [
            event
            for event in delta_events
            if event.payload["message_id"] == str(message.id)
        ]
        provider_chunks = preview_text_chunks(message.content, max_characters=1)
        assert "".join(str(event.payload["delta"]) for event in matching_events) == message.content
        assert [event.payload["delta_index"] for event in matching_events] == list(
            range(1, len(matching_events) + 1)
        )
        assert len(matching_events) == math.ceil(
            len(provider_chunks) / DURABLE_DELTA_BATCH_MAX_CHUNKS
        )
        assert visible_by_message[message.id] == message.content

    assert any(len(str(event.payload["delta"])) > 1 for event in delta_events)


def test_interrupted_stream_never_persists_an_incomplete_canonical_message() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    judge_provider = DeterministicDebateProvider()
    broker = InMemoryDebateEventBroker()
    orchestrator = DebateOrchestrator(
        repository,
        judge_provider,
        judge_provider,
        streaming_turn_provider=InterruptingStreamProvider(),
        event_publisher=broker,
        clock=StepClock(),
    )

    with pytest.raises(DebateOrchestrationError) as error:
        asyncio.run(orchestrator.execute_job_streaming(job.id))

    messages = repository.list_messages(
        queued.id,
        queued.user_id,
        branch_id=queued.active_branch_id,
    )
    events = broker.replay(queued.id)
    failed_session = repository.get_session(queued.id, queued.user_id)
    failed_job = repository.get_job(job.id)

    assert str(error.value) == "Debate streaming job execution failed"
    assert "private upstream" not in str(error.value)
    assert messages == []
    assert any(event.type == "turn.delta" for event in events)
    assert not any(event.type == "turn.completed" for event in events)
    assert events[-1].type == "session.failed"
    assert "private upstream disconnect" not in "".join(
        event.model_dump_json() for event in events
    )
    assert failed_session is not None and failed_session.status == "failed"
    assert failed_job is not None and failed_job.status == "failed"
    assert failed_job.provider_request_count == 1


def test_failed_checkpointed_stream_never_emits_an_unflushed_delta() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    judge_provider = DeterministicDebateProvider()
    broker = InMemoryDebateEventBroker()
    orchestrator = DebateOrchestrator(
        repository,
        judge_provider,
        judge_provider,
        streaming_turn_provider=InterruptingStreamProvider(),
        checkpoint_drafts=True,
        event_publisher=broker,
        clock=StepClock(),
    )

    with pytest.raises(DebateOrchestrationError):
        asyncio.run(orchestrator.execute_job_streaming(job.id))

    events = broker.replay(queued.id)
    assert not any(event.type == "turn.delta" for event in events)
    assert not any(event.type == "turn.completed" for event in events)
    assert events[-1].type == "session.failed"


def test_retryable_stream_failure_leaves_canonical_work_active() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    judge_provider = DeterministicDebateProvider()
    broker = InMemoryDebateEventBroker()
    orchestrator = DebateOrchestrator(
        repository,
        judge_provider,
        judge_provider,
        streaming_turn_provider=RetryableStreamProvider(),
        event_publisher=broker,
        clock=StepClock(),
    )

    with pytest.raises(DebateRetryableOrchestrationError) as error:
        asyncio.run(orchestrator.execute_job_streaming(job.id))

    stored_session = repository.get_session(queued.id, queued.user_id)
    stored_job = repository.get_job(job.id)
    assert str(error.value) == "Debate provider is temporarily unavailable"
    assert "private" not in str(error.value)
    assert error.value.retry_after_seconds == 4
    assert error.value.provider_request_count == 1
    assert stored_session is not None and stored_session.status == "running_round_1"
    assert stored_job is not None and stored_job.status == "running"
    assert not any(event.type == "session.failed" for event in broker.replay(queued.id))


def test_retry_resumes_after_complete_turn_prefix_without_duplicates() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    provider = RetryOnceAfterTwoTurnsProvider()
    judge_provider = DeterministicDebateProvider()
    broker = InMemoryDebateEventBroker()
    orchestrator = DebateOrchestrator(
        repository,
        judge_provider,
        judge_provider,
        streaming_turn_provider=provider,
        event_publisher=broker,
        clock=StepClock(),
    )

    with pytest.raises(DebateRetryableOrchestrationError) as error:
        asyncio.run(orchestrator.execute_job_streaming(job.id))
    first_messages = repository.list_messages(
        queued.id,
        queued.user_id,
        branch_id=queued.active_branch_id,
    )
    repository.requeue_running_job(
        job.id,
        expected_attempt_count=1,
        provider_request_count=error.value.provider_request_count,
        prompt_tokens=error.value.prompt_tokens,
        completion_tokens=error.value.completion_tokens,
    )

    completed = asyncio.run(orchestrator.execute_job_streaming(job.id))
    messages = repository.list_messages(
        queued.id,
        queued.user_id,
        branch_id=queued.active_branch_id,
    )
    completed_job = repository.get_job(job.id)
    started_events = [
        event for event in broker.replay(queued.id) if event.type == "job.started"
    ]

    assert len(first_messages) == 2
    assert completed.status == "awaiting_user"
    assert len(messages) == len({message.id for message in messages}) == 7
    assert completed_job is not None and completed_job.attempt_count == 2
    assert completed_job.provider_request_count == 8
    assert [event.payload["resumed_turn_count"] for event in started_events] == [0, 2]


def test_cancellation_drops_late_stream_output_and_never_marks_failure() -> None:
    async def run_scenario() -> None:
        repository = InMemoryDebateRepository()
        queued, job = build_queued_round_one()
        repository.create_session_with_job(queued, job)
        provider = CancellationBoundaryStreamProvider()
        judge_provider = DeterministicDebateProvider()
        broker = InMemoryDebateEventBroker()
        orchestrator = DebateOrchestrator(
            repository,
            judge_provider,
            judge_provider,
            streaming_turn_provider=provider,
            event_publisher=broker,
            clock=StepClock(),
        )

        execution = asyncio.create_task(orchestrator.execute_job_streaming(job.id))
        await asyncio.wait_for(provider.first_delta_sent.wait(), timeout=1)
        requested = orchestrator.request_cancellation(
            queued.id,
            queued.user_id,
            queued.active_generation_id,
        )
        assert requested.status == "cancel_requested"

        provider.release_late_output.set()
        cancelled = await asyncio.wait_for(execution, timeout=1)
        messages = repository.list_messages(
            queued.id,
            queued.user_id,
            branch_id=queued.active_branch_id,
        )
        stored_job = repository.get_job(job.id)
        events = broker.replay(queued.id)

        assert cancelled.status == "cancelled"
        assert messages == []
        assert stored_job is not None and stored_job.status == "cancelled"
        assert stored_job.provider_request_count == 1
        assert any(event.type == "turn.delta" for event in events)
        assert any(event.type == "session.cancel_requested" for event in events)
        assert events[-1].type == "session.cancelled"
        assert not any(event.type == "turn.completed" for event in events)
        assert not any(event.type == "session.failed" for event in events)

    asyncio.run(run_scenario())


def test_cancellation_during_judge_closes_stream_and_does_not_persist_summary() -> None:
    async def run_scenario() -> None:
        repository = InMemoryDebateRepository()
        queued, job = build_queued_round_one()
        repository.create_session_with_job(queued, job)
        turn_provider = DeterministicStreamingDebateProvider(max_chunk_characters=64)
        judge_provider = CancellationBoundaryJudgeProvider()
        broker = InMemoryDebateEventBroker()
        orchestrator = DebateOrchestrator(
            repository,
            turn_provider,
            turn_provider,
            streaming_turn_provider=turn_provider,
            streaming_judge_provider=judge_provider,
            event_publisher=broker,
            clock=StepClock(),
        )

        execution = asyncio.create_task(orchestrator.execute_job_streaming(job.id))
        await asyncio.wait_for(judge_provider.first_delta_sent.wait(), timeout=1)
        orchestrator.request_cancellation(
            queued.id,
            queued.user_id,
            queued.active_generation_id,
        )
        judge_provider.release_late_output.set()
        cancelled = await asyncio.wait_for(execution, timeout=1)
        await asyncio.wait_for(judge_provider.stream_closed.wait(), timeout=1)

        messages = repository.list_messages(
            queued.id,
            queued.user_id,
            branch_id=queued.active_branch_id,
        )
        events = broker.replay(queued.id)
        assert cancelled.status == "cancelled"
        assert len(messages) == 6
        assert not any(message.role == "judge" for message in messages)
        assert any(event.type == "judge.delta" for event in events)
        assert not any(event.type == "judge.completed" for event in events)
        assert not any(event.type == "session.failed" for event in events)

    asyncio.run(run_scenario())


def test_interruption_preserves_prefix_and_cancels_worker_without_failure() -> None:
    async def run_scenario() -> None:
        repository = InMemoryDebateRepository()
        queued, job = build_queued_round_one()
        repository.create_session_with_job(queued, job)
        provider = CancellationBoundaryStreamProvider()
        judge_provider = DeterministicDebateProvider()
        broker = InMemoryDebateEventBroker()
        orchestrator = DebateOrchestrator(
            repository,
            judge_provider,
            judge_provider,
            streaming_turn_provider=provider,
            checkpoint_drafts=True,
            event_publisher=broker,
            clock=StepClock(),
        )

        execution = asyncio.create_task(orchestrator.execute_job_streaming(job.id))
        await asyncio.wait_for(provider.first_delta_sent.wait(), timeout=1)
        delta = next(event for event in broker.replay(queued.id) if event.type == "turn.delta")
        prefix = delta.payload["delta"][:3]
        repository.interrupt_generation(queued.id, queued.user_id, queued.active_generation_id,
            UUID(delta.payload["message_id"]), prefix, queued.updated_at)

        provider.release_late_output.set()
        cancelled = await asyncio.wait_for(execution, timeout=1)
        messages = repository.list_messages(
            queued.id,
            queued.user_id,
            branch_id=queued.active_branch_id,
        )
        stored_job = repository.get_job(job.id)
        events = broker.replay(queued.id)

        assert cancelled.status == "interrupted_awaiting_user"
        assert len(messages) == 1
        assert messages[0].content == prefix
        assert not messages[0].is_complete
        assert stored_job is not None and stored_job.status == "cancelled"
        assert stored_job.provider_request_count == 1
        assert any(event.type == "turn.delta" for event in events)
        assert sum(event.type == "turn.delta" for event in events) == 1
        assert not any(event.type == "turn.completed" for event in events)
        assert not any(event.type == "session.failed" for event in events)

    asyncio.run(run_scenario())


def test_before_output_stop_discards_an_uncheckpointed_pending_delta() -> None:
    async def run_scenario() -> None:
        repository = InMemoryDebateRepository()
        queued, job = build_queued_round_one()
        repository.create_session_with_job(queued, job)
        provider = CancellationBoundaryStreamProvider(pause_after_chunks=1)
        judge_provider = DeterministicDebateProvider()
        broker = InMemoryDebateEventBroker()
        orchestrator = DebateOrchestrator(
            repository,
            judge_provider,
            judge_provider,
            streaming_turn_provider=provider,
            checkpoint_drafts=True,
            event_publisher=broker,
            clock=StepClock(),
        )

        execution = asyncio.create_task(orchestrator.execute_job_streaming(job.id))
        await asyncio.wait_for(provider.first_delta_sent.wait(), timeout=1)
        assert not any(
            event.type == "turn.delta" for event in broker.replay(queued.id)
        )

        stopped = repository.interrupt_before_output_generation(
            queued.id,
            queued.user_id,
            queued.active_generation_id,
            queued.updated_at,
        )
        provider.release_late_output.set()
        completed = await asyncio.wait_for(execution, timeout=1)
        messages = repository.list_messages(
            queued.id,
            queued.user_id,
            branch_id=queued.active_branch_id,
        )
        events = broker.replay(queued.id)

        assert completed == stopped
        assert completed.status == "interrupted_awaiting_user"
        assert len(messages) == 1
        assert messages[0].content == ""
        assert messages[0].metadata == {"interrupted": True, "before_output": True}
        assert not any(event.type == "turn.delta" for event in events)
        assert not any(event.type == "turn.completed" for event in events)
        assert not any(event.type == "session.failed" for event in events)

    asyncio.run(run_scenario())
