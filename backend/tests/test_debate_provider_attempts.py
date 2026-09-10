from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.domain.debate import DebateDraftCheckpoint, ProviderAttempt
from app.repositories.debate_repository import DebateConcurrencyError
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_state import request_session_cancellation
from test_debate_domain import BRANCH_ID, GENERATION_ID, NOW, SESSION_ID, USER_ID, build_session
from test_memory_debate_repository import store_running_round_one


def build_attempt(*, message_id: UUID) -> ProviderAttempt:
    return ProviderAttempt(
        id=uuid4(),
        session_id=SESSION_ID,
        generation_id=GENERATION_ID,
        message_id=message_id,
        role="bull",
        provider="test-provider",
        model="test-model",
        admitted_at=NOW + timedelta(seconds=3),
    )


def build_checkpoint(*, message_id: UUID) -> DebateDraftCheckpoint:
    return DebateDraftCheckpoint(
        message_id=message_id,
        session_id=SESSION_ID,
        branch_id=BRANCH_ID,
        generation_id=GENERATION_ID,
        sequence_number=1,
        round_number=1,
        exchange_number=1,
        role="bull",
        message_kind="argument",
        content="",
        created_at=NOW + timedelta(seconds=3),
    )


def test_attempt_usage_stays_unknown_until_complete_and_late_usage_keeps_failure() -> None:
    repository = InMemoryDebateRepository()
    session = store_running_round_one(repository)
    message_id = UUID("00000000-0000-4000-8000-000000000201")
    attempt = repository.admit_provider_attempt(
        build_attempt(message_id=message_id),
        build_checkpoint(message_id=message_id),
    )

    dispatched = repository.mark_provider_attempt_dispatched(
        attempt.id, NOW + timedelta(seconds=4)
    )
    failed = repository.finish_provider_attempt(
        dispatched.id, at=NOW + timedelta(seconds=5), failed=True
    )
    assert failed.outcome == "failed"
    assert failed.usage_status == "unknown"
    assert failed.prompt_tokens is None
    assert failed.completion_tokens is None
    assert failed.total_tokens is None

    settled = repository.finish_provider_attempt(
        failed.id,
        at=NOW + timedelta(seconds=6),
        prompt_tokens=7,
        completion_tokens=3,
        total_tokens=10,
    )
    assert settled.outcome == "failed"
    assert settled.usage_status == "reported"
    assert (settled.prompt_tokens, settled.completion_tokens, settled.total_tokens) == (7, 3, 10)
    assert repository.get_session(session.id, session.user_id) == session

    # Usage settlement is idempotent. A repeated report, including a
    # contradictory late report, cannot rewrite the first accepted usage or
    # terminal outcome.
    repeated = repository.finish_provider_attempt(
        settled.id,
        at=NOW + timedelta(seconds=7),
        prompt_tokens=7,
        completion_tokens=3,
        total_tokens=10,
        failed=True,
    )
    contradictory = repository.finish_provider_attempt(
        settled.id,
        at=NOW + timedelta(seconds=8),
        prompt_tokens=8,
        completion_tokens=2,
        total_tokens=10,
        failed=True,
    )
    invalid_late_report = repository.finish_provider_attempt(
        settled.id,
        at=NOW + timedelta(seconds=9),
        prompt_tokens=8,
        completion_tokens=2,
        total_tokens=11,
        failed=True,
    )
    assert repeated == settled
    assert contradictory == settled
    assert invalid_late_report == settled


def test_admission_rejects_a_checkpoint_from_the_other_round() -> None:
    repository = InMemoryDebateRepository()
    store_running_round_one(repository)
    message_id = UUID("00000000-0000-4000-8000-000000000204")

    with pytest.raises(DebateConcurrencyError, match="generation"):
        repository.admit_provider_attempt(
            build_attempt(message_id=message_id),
            build_checkpoint(message_id=message_id).model_copy(update={"round_number": 2}),
        )


def test_interrupt_generation_keeps_provider_attempt_ledger_for_late_settlement() -> None:
    repository = InMemoryDebateRepository()
    session = store_running_round_one(repository)
    message_id = UUID("00000000-0000-4000-8000-000000000205")
    attempt = repository.admit_provider_attempt(
        build_attempt(message_id=message_id),
        build_checkpoint(message_id=message_id),
    )
    repository.mark_provider_attempt_dispatched(attempt.id, NOW + timedelta(seconds=4))
    repository.checkpoint_draft(
        build_checkpoint(message_id=message_id).model_copy(update={"content": "Visible draft output"})
    )

    interrupted = repository.interrupt_generation(
        session.id,
        session.user_id,
        session.active_generation_id,
        message_id,
        "Visible draft",
        NOW + timedelta(seconds=5),
    )
    assert interrupted.status == "interrupted_awaiting_user"
    saved_messages = repository.list_messages(session.id, session.user_id, branch_id=session.active_branch_id)
    assert len(saved_messages) == 1
    assert saved_messages[0].content == "Visible draft"

    failed = repository.finish_provider_attempt(
        attempt.id,
        at=NOW + timedelta(seconds=6),
        failed=True,
    )
    assert failed.outcome == "failed"
    assert [row.id for row in repository.list_provider_attempts(session.id, session.user_id)] == [attempt.id]


def test_stop_keeps_provider_attempt_ledger_but_blocks_new_admission() -> None:
    repository = InMemoryDebateRepository()
    session = store_running_round_one(repository)
    message_id = UUID("00000000-0000-4000-8000-000000000202")
    attempt = repository.admit_provider_attempt(
        build_attempt(message_id=message_id),
        build_checkpoint(message_id=message_id),
    )
    repository.mark_provider_attempt_dispatched(attempt.id, NOW + timedelta(seconds=4))

    requested, cancelled_generation = request_session_cancellation(
        session, at=NOW + timedelta(seconds=5)
    )
    repository.update_session(requested, expected_status=session.status)

    with pytest.raises(DebateConcurrencyError, match="generation"):
        repository.admit_provider_attempt(
            ProviderAttempt(
                id=uuid4(),
                session_id=session.id,
                generation_id=cancelled_generation,
                message_id=uuid4(),
                role="bear",
                provider="test-provider",
                model="test-model",
                admitted_at=NOW + timedelta(seconds=6),
            ),
            DebateDraftCheckpoint(
                message_id=uuid4(),
                session_id=session.id,
                branch_id=session.active_branch_id,
                generation_id=cancelled_generation,
                sequence_number=2,
                round_number=1,
                exchange_number=1,
                role="bear",
                message_kind="rebuttal",
                created_at=NOW + timedelta(seconds=6),
            ),
        )

    rows = repository.list_provider_attempts(session.id, session.user_id)
    assert [row.id for row in rows] == [attempt.id]


def test_attempt_admission_seeds_empty_checkpoint_atomically() -> None:
    repository = InMemoryDebateRepository()
    store_running_round_one(repository)
    message_id = UUID("00000000-0000-4000-8000-000000000203")
    attempt = repository.admit_provider_attempt(
        build_attempt(message_id=message_id),
        build_checkpoint(message_id=message_id),
    )

    assert repository.list_provider_attempts(SESSION_ID, USER_ID) == [attempt]
    with pytest.raises(DebateConcurrencyError, match="generation"):
        repository.checkpoint_draft(
            build_checkpoint(message_id=message_id).model_copy(update={"generation_id": uuid4()})
        )


def test_admission_retry_returns_the_same_row_after_dispatch() -> None:
    repository = InMemoryDebateRepository()
    store_running_round_one(repository)
    message_id = UUID("00000000-0000-4000-8000-000000000206")
    attempt = build_attempt(message_id=message_id)
    checkpoint = build_checkpoint(message_id=message_id)
    admitted = repository.admit_provider_attempt(attempt, checkpoint)
    dispatched = repository.mark_provider_attempt_dispatched(
        admitted.id, NOW + timedelta(seconds=4),
    )
    repository.checkpoint_draft(checkpoint.model_copy(update={"content": "partial"}))

    # A request retry still carries the original admission payload.  The
    # mutable dispatch state must not turn that retry into a duplicate error.
    assert repository.admit_provider_attempt(attempt, checkpoint) == dispatched
