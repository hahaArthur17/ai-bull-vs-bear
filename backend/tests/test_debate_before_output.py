from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest

from app.domain.debate import DebateDraftCheckpoint, DebateMessage
from app.repositories.debate_repository import DebateConcurrencyError
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_state import transition_session
from test_debate_orchestrator import build_queued_round_one


def test_queued_before_output_stop_keeps_prior_transcript_and_cancels_job() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)

    stopped = repository.interrupt_before_output_generation(
        queued.id, queued.user_id, queued.active_generation_id, queued.updated_at,
    )

    assert stopped.status == "interrupted_awaiting_user"
    assert stopped.active_generation_id != queued.active_generation_id
    anchor = repository.list_messages(stopped.id, stopped.user_id, branch_id=stopped.active_branch_id)
    assert len(anchor) == 1
    assert anchor[0].id == queued.active_generation_id
    assert anchor[0].content == ""
    assert not anchor[0].is_complete
    assert anchor[0].cancelled_at is not None
    assert anchor[0].metadata == {"interrupted": True, "before_output": True}
    assert repository.get_job(job.id).status == "cancelled"


def test_before_output_stop_is_stable_on_retry() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    first = repository.interrupt_before_output_generation(
        queued.id, queued.user_id, queued.active_generation_id, queued.updated_at,
    )

    replay = repository.interrupt_before_output_generation(
        queued.id, queued.user_id, queued.active_generation_id, queued.updated_at,
    )

    assert replay == first
    assert len(repository.list_messages(first.id, first.user_id, branch_id=first.active_branch_id)) == 1


def test_before_output_stop_rejects_non_empty_current_generation_draft() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    running = transition_session(
        queued, "running_round_1", at=queued.updated_at + timedelta(seconds=1),
    )
    repository.update_session(running, expected_status="queued_round_1")
    checkpoint = DebateDraftCheckpoint(
        message_id=uuid4(), session_id=running.id, branch_id=running.active_branch_id,
        generation_id=running.active_generation_id, sequence_number=1, round_number=1,
        exchange_number=1, role="bull", message_kind="argument", content="already visible",
        created_at=running.updated_at,
    )
    repository.checkpoint_draft(checkpoint)

    with pytest.raises(DebateConcurrencyError, match="already produced output"):
        repository.interrupt_before_output_generation(
            running.id, running.user_id, running.active_generation_id, running.updated_at,
        )

    current = repository.get_session(running.id, running.user_id)
    assert current == running
    assert repository.get_job(job.id).status == "queued"


def test_before_output_stop_rejects_wrong_owner() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)

    with pytest.raises(DebateConcurrencyError):
        repository.interrupt_before_output_generation(
            queued.id, uuid4(), queued.active_generation_id, queued.updated_at,
        )


def test_before_output_anchor_id_cannot_overwrite_another_session() -> None:
    repository = InMemoryDebateRepository()
    queued, job = build_queued_round_one()
    repository.create_session_with_job(queued, job)
    other, other_job = build_queued_round_one()
    other = other.model_copy(update={"id": uuid4(), "user_id": uuid4()})
    other_job = other_job.model_copy(update={
        "id": uuid4(), "session_id": other.id, "user_id": other.user_id,
        "idempotency_key": f"round-1:{other.id}:{other.active_branch_id}",
    })
    repository.create_session_with_job(other, other_job)

    # Simulate a foreign anchor collision before the requested generation is
    # stopped. The operation must never replace data from another session.
    foreign_anchor = DebateMessage(
        id=queued.active_generation_id, session_id=other.id, branch_id=other.active_branch_id,
        generation_id=other.active_generation_id, sequence_number=1, round_number=1,
        exchange_number=1, role="bull", message_kind="argument", content="",
        is_complete=False, cancelled_at=other.updated_at, metadata={"interrupted": True, "before_output": True},
        created_at=other.updated_at,
    )
    repository._messages[foreign_anchor.id] = foreign_anchor

    with pytest.raises(DebateConcurrencyError, match="collision"):
        repository.interrupt_before_output_generation(
            queued.id, queued.user_id, queued.active_generation_id, queued.updated_at,
        )
