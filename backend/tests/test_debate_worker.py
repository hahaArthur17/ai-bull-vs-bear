from __future__ import annotations

import asyncio
from datetime import timedelta

from app.domain.jobs import ClaimedDebateQueueMessage, DebateQueueMessage
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_orchestrator import DebateOrchestrator
from app.services.debate_worker import DebateWorker
from test_debate_orchestrator import FailingProvider, StepClock, build_queued_round_one


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
