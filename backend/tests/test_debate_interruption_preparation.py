from datetime import timedelta
from uuid import uuid4

import pytest

from app.repositories.debate_repository import DebateConcurrencyError
from app.services.debate_interruption import prepare_interjection, prepare_continuation
from test_debate_interruption import setup_draft, stop
from test_debate_domain import NOW


def paused():
    repo, session, message = setup_draft()
    waiting = stop(repo, session, message)
    transcript = repo.list_messages(session.id, session.user_id, branch_id=session.active_branch_id)
    return waiting, transcript


def test_interjection_does_not_restart_and_continue_keeps_snapshot():
    session, transcript = paused()
    point = prepare_interjection(session, transcript, expected_generation_id=session.active_generation_id,
        content='What about downside risk?', idempotency_key='point-0001', at=NOW + timedelta(seconds=6))
    assert session.status == 'interrupted_awaiting_user'
    transcript.append(point)
    assert prepare_interjection(session, transcript, expected_generation_id=session.active_generation_id,
        content=point.content, idempotency_key='point-0001', at=NOW + timedelta(seconds=7)) == point
    queued, job, envelope = prepare_continuation(session, transcript,
        expected_generation_id=session.active_generation_id, interjection_id=point.id,
        idempotency_key='continue-0001', at=NOW + timedelta(seconds=7))
    assert queued.status == 'queued_round_1'
    assert queued.active_generation_id != session.active_generation_id
    assert queued.analysis_context == session.analysis_context
    assert queued.factor_snapshot == session.factor_snapshot
    assert job.id == envelope.job_id
    assert job.provider_request_count == 0


def test_continue_rejects_expired_snapshot_missing_point_and_wrong_generation():
    session, transcript = paused()
    for generation, stamp in [(uuid4(), NOW), (session.active_generation_id, NOW + timedelta(hours=1)),
                              (session.active_generation_id, NOW + timedelta(seconds=8))]:
        with pytest.raises(DebateConcurrencyError):
            prepare_continuation(session, transcript, expected_generation_id=generation,
                interjection_id=uuid4(), idempotency_key='continue-0001', at=stamp)
