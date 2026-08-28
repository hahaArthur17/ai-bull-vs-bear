from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from app.domain.agents import (
    DebateTurnRequest,
    DebateTurnStreamCompleted,
    DebateTurnStreamDelta,
    DebateTurnStreamEvent,
    DebateTurnStreamUsage,
)
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.providers.streaming_debate import DeterministicStreamingDebateProvider
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_event_broker import InMemoryDebateEventBroker
from app.services.debate_orchestrator import DebateOrchestrationError, DebateOrchestrator
from app.services.debate_orchestrator import DebateRetryableOrchestrationError
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
            error.retry_after_seconds = 1  # type: ignore[attr-defined]
            raise error
        async for event in super().stream_turn(request):
            yield event


class CancellationBoundaryStreamProvider(DeterministicStreamingDebateProvider):
    def __init__(self) -> None:
        super().__init__(max_chunk_characters=32)
        self.first_delta_sent = asyncio.Event()
        self.release_late_output = asyncio.Event()

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        first_delta = True
        async for event in super().stream_turn(request):
            yield event
            if first_delta and event.kind == "delta":
                first_delta = False
                self.first_delta_sent.set()
                await self.release_late_output.wait()


def test_async_orchestrator_streams_then_persists_complete_messages_and_usage() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    provider = TokenRecordingStreamProvider(max_chunk_characters=32)
    broker = InMemoryDebateEventBroker()
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        streaming_turn_provider=provider,
        event_publisher=broker,
        clock=StepClock(),
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
    assert len(messages) == 7
    assert all(message.is_complete for message in messages)
    assert all(
        message.metadata.get("stream_mode") == "async_provider"
        for message in messages
        if message.role in {"bull", "bear"}
    )
    assert sum(event.type == "turn.completed" for event in events) == 6
    assert all(
        event.payload["source"] == "deterministic"
        for event in events
        if event.type == "turn.delta"
    )
    assert events[-1].payload["execution_mode"] == "async_stream"
    assert stored_job is not None
    assert stored_job.provider_request_count == 7
    assert stored_job.prompt_tokens == 18
    assert stored_job.completion_tokens == 12
    assert stored_job.total_tokens == 30

    event_count = len(events)
    assert asyncio.run(orchestrator.execute_job_streaming(job.id)) == session
    assert len(broker.replay(session.id)) == event_count


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
