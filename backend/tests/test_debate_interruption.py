from datetime import timedelta
from uuid import uuid4

import pytest

from app.repositories.debate_repository import DebateConcurrencyError
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from test_memory_debate_repository import build_message, store_running_round_one
from test_debate_domain import NOW


def setup_draft():
    repo = InMemoryDebateRepository()
    session = store_running_round_one(repo)
    message = build_message(content='Hello 世界 trailing text')
    repo.checkpoint_draft(message)
    return repo, session, message


def stop(repo, session, message, prefix='Hello 世界 '):
    return repo.interrupt_generation(session.id, session.user_id,
        session.active_generation_id, message.id, prefix, NOW + timedelta(seconds=5))


def test_stop_preserves_exact_visible_prefix_and_is_idempotent():
    repo, session, message = setup_draft()
    result = stop(repo, session, message)
    assert result.status == 'interrupted_awaiting_user'
    assert result.active_generation_id != session.active_generation_id
    saved, = repo.list_messages(session.id, session.user_id, branch_id=session.active_branch_id)
    assert saved.content == 'Hello 世界 '
    assert saved.is_complete is False
    assert saved.metadata == {'interrupted': True}
    assert stop(repo, session, message) == result
    with pytest.raises(DebateConcurrencyError):
        repo.checkpoint_draft(message)
    with pytest.raises(DebateConcurrencyError):
        repo.append_message(build_message(id=uuid4(), sequence_number=2))


@pytest.mark.parametrize('prefix', ['invented', 'Hello 世界 trailing text plus'])
def test_stop_rejects_content_not_generated(prefix):
    repo, session, message = setup_draft()
    with pytest.raises(DebateConcurrencyError):
        stop(repo, session, message, prefix)
    assert repo.get_session(session.id, session.user_id) == session


def test_stop_rejects_foreign_owner_and_stale_generation():
    repo, session, message = setup_draft()
    for owner, generation in [(uuid4(), session.active_generation_id), (session.user_id, uuid4())]:
        with pytest.raises(DebateConcurrencyError):
            repo.interrupt_generation(session.id, owner, generation, message.id, 'Hello', NOW)


def test_canonical_completion_before_stop_still_freezes_visible_prefix():
    repo, session, message = setup_draft()
    repo.append_message(message)
    later = build_message(id=uuid4(), sequence_number=2, role='bear')
    repo.append_message(later)
    stop(repo, session, message)
    messages = repo.list_messages(session.id, session.user_id, branch_id=session.active_branch_id)
    assert len(messages) == 1
    assert messages[0].content == 'Hello 世界 '
    assert messages[0].is_complete is False


def test_checkpoint_requires_append_only_output():
    repo, session, message = setup_draft()
    with pytest.raises(DebateConcurrencyError):
        repo.checkpoint_draft(message.model_copy(update={'content': 'Replacement'}))
    repo.checkpoint_draft(message.model_copy(update={'content': message.content + ' more'}))
    stop(repo, session, message, message.content + ' ')


def test_stop_can_preserve_empty_visible_prefix():
    repo, session, message = setup_draft()
    stop(repo, session, message, '')
    saved, = repo.list_messages(session.id, session.user_id, branch_id=session.active_branch_id)
    assert saved.content == '' and not saved.is_complete
