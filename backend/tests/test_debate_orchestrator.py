from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.domain.agents import DebateJudgeRequest, DebateTurnRequest
from app.domain.debate import DebateIntervention, DebateSession
from app.domain.factors import FactorSnapshot
from app.domain.jobs import DebateJob
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_orchestrator import DebateOrchestrationError, DebateOrchestrator
from app.services.debate_event_broker import InMemoryDebateEventBroker
from app.services.debate_state import transition_session
from app.services.factor_registry import FactorRegistry
from app.providers.evidence_factors import FilingFactorProvider, NewsFactorProvider
from test_current_factor_providers import build_current_context
from test_debate_domain import BRANCH_ID, GENERATION_ID, NOW, SESSION_ID, USER_ID


ROUND_ONE_JOB_ID = UUID("00000000-0000-4000-8000-000000000200")
ROUND_TWO_JOB_ID = UUID("00000000-0000-4000-8000-000000000201")
INTERVENTION_ID = UUID("00000000-0000-4000-8000-000000000202")


class StepClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 27, 13, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        self.current += timedelta(seconds=1)
        return self.current


class RecordingProvider(DeterministicDebateProvider):
    def __init__(self) -> None:
        self.turn_requests: list[DebateTurnRequest] = []
        self.judge_requests: list[DebateJudgeRequest] = []

    def generate_turn(self, request: DebateTurnRequest):
        self.turn_requests.append(request)
        return super().generate_turn(request)

    def generate_judgement(self, request: DebateJudgeRequest):
        self.judge_requests.append(request)
        return super().generate_judgement(request)


class FailingProvider(RecordingProvider):
    def generate_turn(self, request: DebateTurnRequest):
        self.turn_requests.append(request)
        if len(self.turn_requests) == 3:
            raise RuntimeError("private provider failure details")
        return DeterministicDebateProvider.generate_turn(self, request)


def build_queued_round_one() -> tuple[DebateSession, DebateJob]:
    context = build_current_context()
    snapshot = FactorRegistry(
        [NewsFactorProvider(), FilingFactorProvider()],
        expected_categories=("company",),
    ).collect(context)
    created = DebateSession(
        id=SESSION_ID,
        user_id=USER_ID,
        stock_id=1,
        ticker="AAPL",
        mode="demo",
        opening_side="bull",
        initial_question="What factors could contextualize this movement?",
        active_branch_id=BRANCH_ID,
        active_generation_id=GENERATION_ID,
        analysis_context=context,
        factor_snapshot=FactorSnapshot.model_validate(snapshot.model_dump(mode="python")),
        created_at=NOW,
        updated_at=NOW,
    )
    queued = transition_session(
        created,
        "queued_round_1",
        at=NOW + timedelta(seconds=1),
    )
    job = DebateJob(
        id=ROUND_ONE_JOB_ID,
        session_id=queued.id,
        user_id=queued.user_id,
        job_type="round_1",
        idempotency_key=f"round-1:{queued.id}:{queued.active_branch_id}",
        available_at=queued.updated_at,
        created_at=queued.updated_at,
        updated_at=queued.updated_at,
    )
    return queued, job


def build_round_two_job(session: DebateSession) -> DebateJob:
    return DebateJob(
        id=ROUND_TWO_JOB_ID,
        session_id=session.id,
        user_id=session.user_id,
        job_type="round_2",
        idempotency_key=f"round-2:{session.id}:{INTERVENTION_ID}",
        available_at=session.updated_at,
        created_at=session.updated_at,
        updated_at=session.updated_at,
    )


def start_round_one(provider: RecordingProvider | None = None):
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    selected_provider = provider or RecordingProvider()
    orchestrator = DebateOrchestrator(
        repository,
        selected_provider,
        selected_provider,
        clock=StepClock(),
    )
    session = orchestrator.execute_job(job.id)
    return repository, selected_provider, orchestrator, session


def test_round_one_persists_six_mutual_turns_and_interim_judge() -> None:
    repository, provider, orchestrator, session = start_round_one()
    messages = repository.list_messages(
        session.id,
        session.user_id,
        branch_id=session.active_branch_id,
    )

    assert session.status == "awaiting_user"
    assert [message.role for message in messages] == [
        "bull",
        "bear",
        "bull",
        "bear",
        "bull",
        "bear",
        "judge",
    ]
    assert session.interim_judge_message_id == messages[-1].id
    assert len(provider.turn_requests) == 6
    assert len(provider.judge_requests) == 1
    assert provider.judge_requests[0].phase == "interim"
    assert repository.get_job(ROUND_ONE_JOB_ID).status == "completed"
    assert repository.get_job(ROUND_ONE_JOB_ID).provider_request_count == 7
    assert all(message.is_complete for message in messages)
    assert all(
        repository.list_message_evidence(message.id, session.user_id)
        for message in messages
    )

    request_count = len(provider.turn_requests)
    assert orchestrator.execute_job(ROUND_ONE_JOB_ID) == session
    assert len(provider.turn_requests) == request_count


def test_each_rebuttal_request_targets_the_latest_opponent_message() -> None:
    _, provider, _, _ = start_round_one()

    assert provider.turn_requests[0].rebuttal_target_message_id is None
    for request in provider.turn_requests[1:]:
        opponent = "bear" if request.role == "bull" else "bull"
        latest_opponent = next(
            message for message in reversed(request.transcript) if message.role == opponent
        )
        assert request.rebuttal_target_message_id == latest_opponent.id


def test_user_challenge_runs_round_two_and_persists_final_judge() -> None:
    repository, provider, orchestrator, awaiting = start_round_one()
    round_one_messages = repository.list_messages(
        awaiting.id,
        awaiting.user_id,
        branch_id=awaiting.active_branch_id,
    )
    challenge = DebateIntervention(
        id=INTERVENTION_ID,
        session_id=awaiting.id,
        user_id=awaiting.user_id,
        selected_message_id=round_one_messages[-1].id,
        selected_text="competing interpretations",
        question="Which missing evidence could most change both sides' conclusions?",
        mode="challenge",
        created_at=awaiting.updated_at + timedelta(seconds=1),
    )
    queued_round_two = orchestrator.submit_challenge(
        challenge,
        build_round_two_job(awaiting),
    )
    assert (
        orchestrator.submit_challenge(challenge, build_round_two_job(awaiting))
        == queued_round_two
    )
    completed = orchestrator.execute_job(ROUND_TWO_JOB_ID)
    messages = repository.list_messages(
        completed.id,
        completed.user_id,
        branch_id=completed.active_branch_id,
    )

    assert queued_round_two.status == "queued_round_2"
    assert completed.status == "completed"
    assert [message.role for message in messages[7:]] == [
        "user",
        "bull",
        "bear",
        "bull",
        "bear",
        "judge",
    ]
    assert completed.final_judge_message_id == messages[-1].id
    assert provider.judge_requests[-1].phase == "final"
    assert all(
        request.user_intervention == challenge.question
        for request in provider.turn_requests[-4:]
    )
    assert repository.get_job(ROUND_TWO_JOB_ID).status == "completed"
    assert repository.get_job(ROUND_TWO_JOB_ID).provider_request_count == 5


def test_provider_failure_marks_session_and_job_with_safe_codes() -> None:
    provider = FailingProvider()
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        clock=StepClock(),
    )

    with pytest.raises(DebateOrchestrationError) as error:
        orchestrator.execute_job(job.id)

    failed_session = repository.get_session(queued.id, queued.user_id)
    failed_job = repository.get_job(job.id)
    assert "private provider failure" not in str(error.value)
    assert failed_session.status == "failed"
    assert failed_session.safe_error_code == "debate_execution_failed"
    assert failed_job.status == "failed"
    assert failed_job.safe_error_code == "debate_execution_failed"
    assert failed_job.provider_request_count == 3
    assert len(
        repository.list_messages(
            queued.id,
            queued.user_id,
            branch_id=queued.active_branch_id,
        )
    ) == 2


def test_round_one_publishes_ordered_reconstructable_preview_events() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    provider = RecordingProvider()
    broker = InMemoryDebateEventBroker()
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        event_publisher=broker,
        clock=StepClock(),
    )

    session = orchestrator.execute_job(job.id)
    events = broker.replay(session.id)

    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert events[0].type == "job.started"
    assert events[-1].type == "session.awaiting_user"
    assert sum(event.type == "turn.started" for event in events) == 6
    assert sum(event.type == "turn.completed" for event in events) == 6
    assert sum(event.type == "judge.started" for event in events) == 1
    assert sum(event.type == "judge.completed" for event in events) == 1
    assert any(event.type == "turn.citation" for event in events)

    completed_events = [event for event in events if event.type == "turn.completed"]
    for completed_event in completed_events:
        message = completed_event.payload["message"]
        assert isinstance(message, dict)
        message_id = str(message["id"])
        deltas = [
            str(event.payload["delta"])
            for event in events
            if event.type == "turn.delta"
            and event.payload["message_id"] == message_id
        ]
        assert "".join(deltas) == message["content"]
        assert all(
            event.payload["source"] == "buffered_compatibility"
            for event in events
            if event.type == "turn.delta"
            and event.payload["message_id"] == message_id
        )


def test_provider_failure_publishes_only_a_safe_terminal_event() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    provider = FailingProvider()
    broker = InMemoryDebateEventBroker()
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        event_publisher=broker,
        clock=StepClock(),
    )

    with pytest.raises(DebateOrchestrationError):
        orchestrator.execute_job(job.id)

    events = broker.replay(queued.id)
    assert events[-1].type == "session.failed"
    assert events[-1].payload["safe_error_code"] == "debate_execution_failed"
    assert "private provider failure" not in "".join(
        event.model_dump_json() for event in events
    )


def test_transient_event_failure_does_not_block_canonical_workflow() -> None:
    class FailingPublisher:
        def publish(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("event transport unavailable")

    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    provider = RecordingProvider()
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        event_publisher=FailingPublisher(),  # type: ignore[arg-type]
        clock=StepClock(),
    )

    session = orchestrator.execute_job(job.id)

    assert session.status == "awaiting_user"
    assert len(
        repository.list_messages(
            session.id,
            session.user_id,
            branch_id=session.active_branch_id,
        )
    ) == 7


def test_queued_cancellation_is_immediate_idempotent_and_generation_scoped() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    broker = InMemoryDebateEventBroker()
    provider = RecordingProvider()
    orchestrator = DebateOrchestrator(
        repository,
        provider,
        provider,
        event_publisher=broker,
        clock=StepClock(),
    )

    wrong_generation = UUID("00000000-0000-4000-8000-000000000299")
    with pytest.raises(DebateOrchestrationError, match="generation changed"):
        orchestrator.request_cancellation(queued.id, queued.user_id, wrong_generation)
    assert repository.get_session(queued.id, queued.user_id) == queued
    assert repository.get_job(job.id) == job

    cancelled = orchestrator.request_cancellation(
        queued.id,
        queued.user_id,
        queued.active_generation_id,
    )
    repeated = orchestrator.request_cancellation(
        queued.id,
        queued.user_id,
        queued.active_generation_id,
    )

    assert cancelled.status == "cancelled"
    assert repeated == cancelled
    assert cancelled.active_generation_id != queued.active_generation_id
    assert repository.get_job(job.id).status == "cancelled"
    assert [event.type for event in broker.replay(queued.id)] == [
        "session.cancel_requested",
        "session.cancelled",
    ]
