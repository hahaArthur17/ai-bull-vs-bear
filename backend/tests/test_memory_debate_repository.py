from datetime import datetime, timedelta
from uuid import UUID

import pytest

from app.domain.debate import DebateIntervention, DebateMessage, DebateMessageEvidence, DebateSession
from app.domain.jobs import DebateJob, DebateQueueMessage
from app.repositories.debate_repository import (
    DebateConcurrencyError,
    DebateRepositoryError,
    DebateQueueRepository,
    DebateUnitOfWork,
)
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_state import transition_session
from test_debate_domain import BRANCH_ID, GENERATION_ID, NOW, SESSION_ID, USER_ID, build_session


OTHER_USER_ID = UUID("00000000-0000-4000-8000-000000000099")
JOB_ID = UUID("00000000-0000-4000-8000-000000000100")
MESSAGE_ID = UUID("00000000-0000-4000-8000-000000000101")


def build_job(session: DebateSession, **updates: object) -> DebateJob:
    return DebateJob.model_validate(
        {
            "id": JOB_ID,
            "session_id": session.id,
            "user_id": session.user_id,
            "job_type": "round_1",
            "status": "queued",
            "idempotency_key": f"round-1:{session.id}:{session.active_branch_id}",
            "available_at": NOW,
            "created_at": NOW,
            "updated_at": NOW,
            **updates,
        }
    )


def build_message(**updates: object) -> DebateMessage:
    return DebateMessage.model_validate(
        {
            "id": MESSAGE_ID,
            "session_id": SESSION_ID,
            "branch_id": BRANCH_ID,
            "generation_id": GENERATION_ID,
            "sequence_number": 1,
            "round_number": 1,
            "exchange_number": 1,
            "role": "bull",
            "message_kind": "argument",
            "content": "A bounded opening argument with explicit uncertainty.",
            "created_at": NOW,
            **updates,
        }
    )


def store_running_round_one(repository: InMemoryDebateRepository) -> DebateSession:
    session = repository.create_session(build_session())
    queued = transition_session(session, "queued_round_1", at=NOW + timedelta(seconds=1))
    repository.update_session(queued, expected_status="created")
    running = transition_session(queued, "running_round_1", at=NOW + timedelta(seconds=2))
    return repository.update_session(running, expected_status="queued_round_1")


def test_memory_repository_implements_the_unit_of_work_contract() -> None:
    assert isinstance(InMemoryDebateRepository(), DebateUnitOfWork)
    assert isinstance(InMemoryDebateRepository(), DebateQueueRepository)


def test_atomic_session_job_creation_is_idempotent_and_owner_scoped() -> None:
    repository = InMemoryDebateRepository()
    session = build_session()
    job = build_job(session)

    created = repository.create_session_with_job(session, job)
    repeated = repository.create_session_with_job(session, job)

    assert created == repeated == (session, job)
    assert repository.get_session(session.id, session.user_id) == session
    assert repository.get_session(session.id, OTHER_USER_ID) is None
    assert repository.list_sessions(OTHER_USER_ID) == []

    mismatched_session = DebateSession.model_validate(
        {
            **session.model_dump(mode="python"),
            "id": UUID("00000000-0000-4000-8000-000000000102"),
        }
    )
    mismatched_job = build_job(
        mismatched_session,
        id=UUID("00000000-0000-4000-8000-000000000103"),
        user_id=OTHER_USER_ID,
        session_id=mismatched_session.id,
        idempotency_key="round-1:mismatched-owner",
    )
    with pytest.raises(DebateRepositoryError, match="owner"):
        repository.create_session_with_job(mismatched_session, mismatched_job)
    assert repository.get_session(mismatched_session.id, mismatched_session.user_id) is None


def test_session_updates_use_optimistic_status_and_domain_transition_rules() -> None:
    repository = InMemoryDebateRepository()
    session = repository.create_session(build_session())
    queued = transition_session(session, "queued_round_1", at=NOW + timedelta(seconds=1))

    assert repository.update_session(queued, expected_status="created") == queued

    running = transition_session(queued, "running_round_1", at=NOW + timedelta(seconds=2))
    with pytest.raises(DebateConcurrencyError, match="concurrently"):
        repository.update_session(running, expected_status="created")

    invalid_repository = InMemoryDebateRepository()
    invalid_repository.create_session(session)
    skipped = DebateSession.model_validate(
        {
            **session.model_dump(mode="python"),
            "status": "running_round_1",
            "updated_at": NOW + timedelta(seconds=1),
        }
    )
    with pytest.raises(DebateRepositoryError, match="Invalid Debate session"):
        invalid_repository.update_session(skipped, expected_status="created")


def test_messages_and_citations_are_atomic_idempotent_and_owner_scoped() -> None:
    repository = InMemoryDebateRepository()
    store_running_round_one(repository)
    message = build_message()
    citation = DebateMessageEvidence(
        message_id=message.id,
        evidence_id="technical-aapl-001",
        citation_order=1,
        support_span="Moving-average context only; not a prediction.",
    )

    assert repository.append_message(message, (citation,)) == message
    assert repository.append_message(message, (citation,)) == message
    assert repository.list_messages(SESSION_ID, USER_ID, branch_id=BRANCH_ID) == [message]
    assert repository.list_messages(SESSION_ID, OTHER_USER_ID, branch_id=BRANCH_ID) == []
    assert repository.list_message_evidence(message.id, USER_ID) == (citation,)
    assert repository.list_message_evidence(message.id, OTHER_USER_ID) == ()

    collision = build_message(
        id=UUID("00000000-0000-4000-8000-000000000104"),
        content="A conflicting message for the same canonical sequence.",
    )
    with pytest.raises(DebateConcurrencyError, match="sequence"):
        repository.append_message(collision)


def test_interventions_must_target_a_message_owned_by_the_same_session_user() -> None:
    repository = InMemoryDebateRepository()
    store_running_round_one(repository)
    message = build_message()
    repository.append_message(message)
    intervention = DebateIntervention(
        id=UUID("00000000-0000-4000-8000-000000000105"),
        session_id=SESSION_ID,
        user_id=USER_ID,
        selected_message_id=message.id,
        selected_text="moving average",
        question="What does this mean here?",
        mode="explain",
        created_at=NOW,
    )

    assert repository.create_intervention(intervention) == intervention
    assert repository.create_intervention(intervention) == intervention

    wrong_owner = DebateIntervention.model_validate(
        {**intervention.model_dump(mode="python"), "user_id": OTHER_USER_ID}
    )
    with pytest.raises(DebateRepositoryError, match="session not found"):
        repository.create_intervention(wrong_owner)


def test_jobs_enforce_idempotency_owner_and_optimistic_state_transitions() -> None:
    repository = InMemoryDebateRepository()
    session = repository.create_session(build_session())
    queued = repository.create_job(build_job(session))
    assert repository.create_job(queued) == queued
    assert repository.get_active_job(session.id, session.user_id) == queued
    assert repository.get_active_job(session.id, OTHER_USER_ID) is None

    second_active = build_job(
        session,
        id=UUID("00000000-0000-4000-8000-000000000109"),
        idempotency_key="round-1:second-active-job",
    )
    with pytest.raises(DebateConcurrencyError, match="active job"):
        repository.create_job(second_active)

    running = DebateJob.model_validate(
        {
            **queued.model_dump(mode="python"),
            "status": "running",
            "attempt_count": 1,
            "started_at": NOW + timedelta(seconds=1),
            "updated_at": NOW + timedelta(seconds=1),
        }
    )
    assert repository.update_job(running, expected_status="queued") == running

    completed = DebateJob.model_validate(
        {
            **running.model_dump(mode="python"),
            "status": "completed",
            "finished_at": NOW + timedelta(seconds=2),
            "updated_at": NOW + timedelta(seconds=2),
        }
    )
    with pytest.raises(DebateConcurrencyError, match="concurrently"):
        repository.update_job(completed, expected_status="queued")

    duplicate_key = build_job(
        session,
        id=UUID("00000000-0000-4000-8000-000000000106"),
    )
    with pytest.raises(DebateConcurrencyError, match="idempotency"):
        repository.create_job(duplicate_key)


def test_new_agent_messages_require_the_current_running_generation() -> None:
    repository = InMemoryDebateRepository()
    running = store_running_round_one(repository)

    with pytest.raises(DebateConcurrencyError, match="generation"):
        repository.append_message(
            build_message(
                generation_id=UUID("00000000-0000-4000-8000-000000000110")
            )
        )

    cancel_requested = transition_session(
        running,
        "cancel_requested",
        at=NOW + timedelta(seconds=3),
    )
    repository.update_session(cancel_requested, expected_status="running_round_1")
    with pytest.raises(DebateConcurrencyError, match="no longer accepts"):
        repository.append_message(build_message())


def test_memory_queue_redelivers_after_visibility_and_archives_idempotently() -> None:
    class MutableClock:
        def __init__(self) -> None:
            self.now = NOW

        def __call__(self) -> datetime:
            return self.now

    clock = MutableClock()
    repository = InMemoryDebateRepository(clock=clock)
    session = transition_session(
        build_session(),
        "queued_round_1",
        at=NOW + timedelta(seconds=1),
    )
    job = build_job(
        session,
        available_at=session.updated_at,
        created_at=session.updated_at,
        updated_at=session.updated_at,
    )
    message = DebateQueueMessage(
        job_id=job.id,
        session_id=session.id,
        job_type=job.job_type,
        trace_id="trace_queue_001",
        enqueued_at=session.updated_at,
    )

    admitted_session, admitted_job = repository.create_session_with_job_and_enqueue(
        session,
        job,
        message,
    )
    repeated = repository.create_session_with_job_and_enqueue(session, job, message)
    assert admitted_session == session
    assert admitted_job.queue_message_id == 1
    assert repeated == (admitted_session, admitted_job)

    first = repository.claim_job(visibility_timeout_seconds=30)
    assert first is not None and first.read_count == 1
    assert repository.claim_job(visibility_timeout_seconds=30) is None

    clock.now += timedelta(seconds=30)
    redelivered = repository.claim_job(visibility_timeout_seconds=30)
    assert redelivered is not None and redelivered.read_count == 2
    assert redelivered.queue_message_id == first.queue_message_id

    assert repository.retry_job_message(first.queue_message_id, delay_seconds=60)
    clock.now += timedelta(seconds=59)
    assert repository.claim_job(visibility_timeout_seconds=30) is None
    clock.now += timedelta(seconds=1)
    assert repository.claim_job(visibility_timeout_seconds=30).read_count == 3

    assert repository.archive_job_message(first.queue_message_id)
    assert repository.archive_job_message(first.queue_message_id)
    assert repository.claim_job(visibility_timeout_seconds=30) is None
    assert not repository.retry_job_message(first.queue_message_id, delay_seconds=0)


def test_memory_queue_rejects_mismatched_admission_without_partial_state() -> None:
    repository = InMemoryDebateRepository(clock=lambda: NOW)
    session = transition_session(
        build_session(),
        "queued_round_1",
        at=NOW + timedelta(seconds=1),
    )
    job = build_job(
        session,
        available_at=session.updated_at,
        created_at=session.updated_at,
        updated_at=session.updated_at,
    )
    wrong_message = DebateQueueMessage(
        job_id=UUID("00000000-0000-4000-8000-000000000199"),
        session_id=session.id,
        job_type=job.job_type,
        trace_id="trace_queue_002",
        enqueued_at=session.updated_at,
    )

    with pytest.raises(DebateRepositoryError, match="does not match"):
        repository.create_session_with_job_and_enqueue(session, job, wrong_message)
    assert repository.get_session(session.id, session.user_id) is None
    assert repository.get_job(job.id) is None
