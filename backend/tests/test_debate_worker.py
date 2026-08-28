from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.jobs import ClaimedDebateQueueMessage, DebateQueueMessage
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.providers.streaming_debate import DeterministicStreamingDebateProvider
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_orchestrator import DebateOrchestrator
from app.services.debate_event_broker import InMemoryDebateEventBroker
from app.services.debate_preview import DebatePreviewService
from app.services.debate_worker import DebateWorker
from test_debate_orchestrator import FailingProvider, StepClock, build_queued_round_one
from test_debate_streaming_orchestrator import RetryOnceAfterTwoTurnsProvider


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


class CrashOnceAfterTwoTurnsProvider(DeterministicStreamingDebateProvider):
    def __init__(self) -> None:
        super().__init__(max_chunk_characters=32)
        self.request_count = 0
        self.crash_boundary = asyncio.Event()
        self.crashed_once = False

    async def stream_turn(self, request):
        self.request_count += 1
        if self.request_count == 3 and not self.crashed_once:
            self.crashed_once = True
            self.crash_boundary.set()
            await asyncio.Event().wait()
        async for event in super().stream_turn(request):
            yield event


class ConcurrencyProbeProvider(DeterministicStreamingDebateProvider):
    def __init__(self, expected_concurrency: int) -> None:
        super().__init__(max_chunk_characters=64)
        self.expected_concurrency = expected_concurrency
        self.active = 0
        self.maximum_active = 0
        self.reached_limit = asyncio.Event()
        self.release = asyncio.Event()

    async def stream_turn(self, request):
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        if self.active == self.expected_concurrency:
            self.reached_limit.set()
        try:
            await self.release.wait()
            async for event in super().stream_turn(request):
                yield event
        finally:
            self.active -= 1


def admit_round_one(repository: InMemoryDebateRepository):
    session, job = build_queued_round_one()
    message = DebateQueueMessage(
        job_id=job.id,
        session_id=session.id,
        job_type=job.job_type,
        trace_id="trace_worker_001",
        enqueued_at=job.created_at,
    )
    return repository.create_session_with_job_and_enqueue(session, job, message)


def build_worker(repository: InMemoryDebateRepository) -> DebateWorker:
    provider = DeterministicDebateProvider()
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        clock=StepClock(),
    )
    return DebateWorker(repository, repository, orchestrator)


def build_streaming_worker(
    repository: InMemoryDebateRepository,
    provider: DeterministicStreamingDebateProvider,
    event_broker: InMemoryDebateEventBroker | None = None,
) -> DebateWorker:
    judge = DeterministicDebateProvider()
    orchestrator = DebateOrchestrator(
        repository,
        judge,
        judge,
        streaming_turn_provider=provider,
        event_publisher=event_broker,
        clock=StepClock(),
    )
    return DebateWorker(
        repository,
        repository,
        orchestrator,
        visibility_timeout_seconds=30,
    )


def test_worker_executes_and_archives_only_after_durable_completion() -> None:
    repository = InMemoryDebateRepository()
    session, job = admit_round_one(repository)
    worker = build_worker(repository)

    first, idle = asyncio.run(worker.run_until_idle(max_messages=2))
    completed_session = repository.get_session(session.id, session.user_id)
    completed_job = repository.get_job(job.id)

    assert first.outcome == "completed"
    assert first.queue_message_id == job.queue_message_id
    assert first.read_count == 1
    assert idle.outcome == "idle"
    assert completed_session is not None and completed_session.status == "awaiting_user"
    assert completed_job is not None and completed_job.status == "completed"
    assert len(
        repository.list_messages(
            session.id,
            session.user_id,
            branch_id=session.active_branch_id,
        )
    ) == 7


def test_worker_archives_redelivery_for_an_already_terminal_job() -> None:
    repository = InMemoryDebateRepository()
    session, job = admit_round_one(repository)
    worker = build_worker(repository)
    assert asyncio.run(worker.run_once()).outcome == "completed"

    payload = DebateQueueMessage(
        job_id=job.id,
        session_id=session.id,
        job_type=job.job_type,
        trace_id="trace_worker_002",
        enqueued_at=job.created_at,
    )

    class DuplicateQueue:
        def __init__(self) -> None:
            self.claimed = False
            self.archived = False

        def claim_job(self, *, visibility_timeout_seconds: int):
            if self.claimed:
                return None
            self.claimed = True
            return ClaimedDebateQueueMessage(
                queue_message_id=job.queue_message_id,
                read_count=2,
                enqueued_at=job.created_at,
                visibility_deadline=job.created_at + timedelta(minutes=15),
                payload=payload,
            )

        def archive_job_message(self, queue_message_id: int) -> bool:
            self.archived = queue_message_id == job.queue_message_id
            return self.archived

    duplicate_queue = DuplicateQueue()
    provider = DeterministicDebateProvider()
    duplicate_worker = DebateWorker(
        repository,
        duplicate_queue,  # type: ignore[arg-type]
        DebateOrchestrator(repository, provider, provider, clock=StepClock()),
    )
    result = asyncio.run(duplicate_worker.run_once())

    assert result.outcome == "skipped_terminal"
    assert duplicate_queue.archived
    assert repository.get_job(job.id).status == "completed"


def test_worker_defers_a_running_job_for_later_recovery() -> None:
    repository = InMemoryDebateRepository()
    _, job = admit_round_one(repository)
    running = repository.get_job(job.id)
    assert running is not None
    from app.services.debate_job_state import start_job

    running = start_job(running, at=running.updated_at)
    repository.update_job(running, expected_status="queued")
    result = asyncio.run(build_worker(repository).run_once())

    assert result.outcome == "deferred_running"
    assert repository.get_job(job.id).status == "running"


def test_worker_archives_a_safely_terminalized_permanent_failure() -> None:
    repository = InMemoryDebateRepository()
    session, job = admit_round_one(repository)
    provider = FailingProvider()
    worker = DebateWorker(
        repository,
        repository,
        DebateOrchestrator(repository, provider, provider, clock=StepClock()),
    )

    failed = asyncio.run(worker.run_once())
    idle = asyncio.run(worker.run_once())

    assert failed.outcome == "failed"
    assert idle.outcome == "idle"
    assert repository.get_job(job.id).status == "failed"
    assert repository.get_session(session.id, session.user_id).status == "failed"


def test_worker_retries_temporary_failure_then_resumes_without_duplicates() -> None:
    clock = MutableClock()
    repository = InMemoryDebateRepository(clock=clock)
    session, job = admit_round_one(repository)
    provider = RetryOnceAfterTwoTurnsProvider()
    broker = InMemoryDebateEventBroker()
    worker = build_streaming_worker(repository, provider, broker)

    retry = asyncio.run(worker.run_once())
    first_messages = repository.list_messages(
        session.id,
        session.user_id,
        branch_id=session.active_branch_id,
    )
    queued_job = repository.get_job(job.id)

    assert retry.outcome == "retry_scheduled"
    assert retry.retry_delay_seconds == 4
    assert len(first_messages) == 2
    assert queued_job is not None and queued_job.status == "queued"
    assert queued_job.attempt_count == 1
    retry_events = [
        event for event in broker.replay(session.id) if event.type == "job.retry_scheduled"
    ]
    assert len(retry_events) == 1
    assert retry_events[0].payload["retry_delay_seconds"] == 4
    assert asyncio.run(worker.run_once()).outcome == "idle"

    clock.now += timedelta(seconds=4)
    completed = asyncio.run(worker.run_once())
    messages = repository.list_messages(
        session.id,
        session.user_id,
        branch_id=session.active_branch_id,
    )
    completed_job = repository.get_job(job.id)

    assert completed.outcome == "completed"
    assert completed.read_count == 2
    assert len(messages) == len({message.id for message in messages}) == 7
    assert completed_job is not None and completed_job.attempt_count == 2
    assert completed_job.provider_request_count == 8


def test_worker_recovers_a_crashed_running_job_after_visibility_timeout() -> None:
    async def run_scenario() -> None:
        clock = MutableClock()
        repository = InMemoryDebateRepository(clock=clock)
        session, job = admit_round_one(repository)
        provider = CrashOnceAfterTwoTurnsProvider()
        broker = InMemoryDebateEventBroker()
        worker = build_streaming_worker(repository, provider, broker)

        interrupted = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(provider.crash_boundary.wait(), timeout=1)
        interrupted.cancel()
        with pytest.raises(asyncio.CancelledError):
            await interrupted

        running_job = repository.get_job(job.id)
        partial = repository.list_messages(
            session.id,
            session.user_id,
            branch_id=session.active_branch_id,
        )
        assert running_job is not None and running_job.status == "running"
        assert len(partial) == 2

        clock.now += timedelta(seconds=30)
        recovered = await worker.run_once()
        messages = repository.list_messages(
            session.id,
            session.user_id,
            branch_id=session.active_branch_id,
        )
        completed_job = repository.get_job(job.id)

        assert recovered.outcome == "completed"
        assert recovered.read_count == 2
        assert len(messages) == len({message.id for message in messages}) == 7
        assert completed_job is not None and completed_job.attempt_count == 2

    asyncio.run(run_scenario())


def test_worker_terminalizes_an_exhausted_crashed_job() -> None:
    async def run_scenario() -> None:
        clock = MutableClock()
        repository = InMemoryDebateRepository(clock=clock)
        session, job = build_queued_round_one()
        job = job.model_copy(update={"max_attempts": 1})

        message = DebateQueueMessage(
            job_id=job.id,
            session_id=session.id,
            job_type=job.job_type,
            trace_id="trace_exhausted_001",
            enqueued_at=job.created_at,
        )
        _, job = repository.create_session_with_job_and_enqueue(session, job, message)
        provider = CrashOnceAfterTwoTurnsProvider()
        broker = InMemoryDebateEventBroker()
        worker = build_streaming_worker(repository, provider, broker)

        interrupted = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(provider.crash_boundary.wait(), timeout=1)
        interrupted.cancel()
        with pytest.raises(asyncio.CancelledError):
            await interrupted
        clock.now += timedelta(seconds=30)

        failed = await worker.run_once()
        failed_job = repository.get_job(job.id)
        failed_session = repository.get_session(session.id, session.user_id)

        assert failed.outcome == "failed"
        assert failed.read_count == 2
        assert failed_job is not None
        assert failed_job.safe_error_code == "debate_retry_exhausted"
        assert failed_session is not None
        assert failed_session.safe_error_code == "debate_retry_exhausted"
        assert [event.type for event in broker.replay(session.id)][-2:] == [
            "job.failed",
            "session.failed",
        ]
        assert (await worker.run_once()).outcome == "idle"

    asyncio.run(run_scenario())


def test_worker_settles_cancellation_after_a_running_process_crash() -> None:
    async def run_scenario() -> None:
        clock = MutableClock()
        repository = InMemoryDebateRepository(clock=clock)
        session, job = admit_round_one(repository)
        provider = CrashOnceAfterTwoTurnsProvider()
        worker = build_streaming_worker(repository, provider)

        interrupted = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(provider.crash_boundary.wait(), timeout=1)
        requested = worker.orchestrator.request_cancellation(
            session.id,
            session.user_id,
            session.active_generation_id,
        )
        assert requested.status == "cancel_requested"
        interrupted.cancel()
        with pytest.raises(asyncio.CancelledError):
            await interrupted

        clock.now += timedelta(seconds=30)
        cancelled = await worker.run_once()
        stored_job = repository.get_job(job.id)
        stored_session = repository.get_session(session.id, session.user_id)
        messages = repository.list_messages(
            session.id,
            session.user_id,
            branch_id=session.active_branch_id,
        )

        assert cancelled.outcome == "cancelled"
        assert cancelled.read_count == 2
        assert stored_job is not None and stored_job.status == "cancelled"
        assert stored_session is not None and stored_session.status == "cancelled"
        assert len(messages) == 2
        assert (await worker.run_once()).outcome == "idle"

    asyncio.run(run_scenario())


def test_two_workers_apply_backpressure_to_three_queued_sessions() -> None:
    async def run_scenario() -> None:
        clock = MutableClock()
        repository = InMemoryDebateRepository(clock=clock)
        probe = ConcurrencyProbeProvider(expected_concurrency=2)
        judge = DeterministicDebateProvider()
        service = DebatePreviewService(
            repository,
            judge,
            judge,
            streaming_turn_provider=probe,
            clock=clock,
        )
        template, _ = build_queued_round_one()
        admitted = [
            service.create_queued_round_one(
                user_id=template.user_id,
                stock_id=template.stock_id,
                ticker=template.ticker,
                opening_side=template.opening_side,
                question=f"Bounded queue question {index}?",
                idempotency_key=f"backpressure_{index:03d}",
                analysis_context=template.analysis_context,
                factor_snapshot=template.factor_snapshot,
            )
            for index in range(3)
        ]
        workers = [
            DebateWorker(
                repository,
                repository,
                service.orchestrator,
                visibility_timeout_seconds=30,
            )
            for _ in range(2)
        ]

        first_wave = [asyncio.create_task(worker.run_once()) for worker in workers]
        await asyncio.wait_for(probe.reached_limit.wait(), timeout=1)
        statuses = [
            repository.get_session(session.id, session.user_id).status
            for session, _ in admitted
        ]

        assert probe.maximum_active == 2
        assert statuses.count("running_round_1") == 2
        assert statuses.count("queued_round_1") == 1

        probe.release.set()
        first_results = await asyncio.gather(*first_wave)
        third_result = await workers[0].run_once()
        final_statuses = [
            repository.get_session(session.id, session.user_id).status
            for session, _ in admitted
        ]

        assert [result.outcome for result in first_results] == ["completed", "completed"]
        assert third_result.outcome == "completed"
        assert final_statuses == ["awaiting_user", "awaiting_user", "awaiting_user"]
        assert probe.maximum_active == 2

    asyncio.run(run_scenario())


def test_worker_loop_stops_cleanly_while_queue_is_idle() -> None:
    async def run_scenario() -> None:
        repository = InMemoryDebateRepository()
        worker = build_worker(repository)
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            worker.run_forever(stop_event, poll_seconds=0.1)
        )
        await asyncio.sleep(0)
        stop_event.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(run_scenario())


def test_worker_loop_rejects_an_unsafe_poll_interval() -> None:
    repository = InMemoryDebateRepository()
    worker = build_worker(repository)

    async def run_scenario() -> None:
        try:
            await worker.run_forever(asyncio.Event(), poll_seconds=0)
        except ValueError as exc:
            assert str(exc) == "Worker poll interval is outside safe bounds"
        else:
            raise AssertionError("Expected an unsafe poll interval to be rejected")

    asyncio.run(run_scenario())
