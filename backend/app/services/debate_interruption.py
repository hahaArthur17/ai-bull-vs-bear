"""Pure preparation for explicit, bounded continuation of a frozen debate."""
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from app.domain.debate import DebateMessage, DebateSession
from app.domain.jobs import DebateJob, DebateQueueMessage
from app.repositories.debate_repository import DebateConcurrencyError

# A continuation is part of the same short-lived captured discussion. It never
# refreshes prices in place. Older research remains readable as historical data.
CONTINUATION_MAX_AGE = timedelta(minutes=30)
MAX_INTERJECTIONS = 6


def interruption_target(transcript: list[DebateMessage]) -> DebateMessage:
    target = next((message for message in reversed(transcript)
                   if not message.is_complete and message.role in {'bull', 'bear', 'judge'}
                   and message.metadata.get('interrupted') is True), None)
    if target is None:
        raise DebateConcurrencyError('No retained interruption point')
    return target


def prepare_interjection(session: DebateSession, transcript: list[DebateMessage], *,
                         expected_generation_id: UUID, content: str,
                         idempotency_key: str, at: datetime) -> DebateMessage:
    if session.status != 'interrupted_awaiting_user' or session.active_generation_id != expected_generation_id:
        raise DebateConcurrencyError('Debate is not waiting at this interruption')
    target = interruption_target(transcript)
    text = content.strip()
    if not text or len(text) > 500:
        raise DebateConcurrencyError('An interjection requires 1 to 500 characters')
    message_id = uuid5(session.id, f'interject:{idempotency_key}')
    existing = next((message for message in transcript if message.id == message_id), None)
    if existing:
        if (existing.content != text or existing.metadata.get('interrupted_message_id') != str(target.id)
                or existing.generation_id != expected_generation_id):
            raise DebateConcurrencyError('Interjection key conflicts with another request')
        return existing
    if sum(message.metadata.get('interjection') is True for message in transcript) >= MAX_INTERJECTIONS:
        raise DebateConcurrencyError('This debate reached its interjection limit')
    return DebateMessage(id=message_id, session_id=session.id, branch_id=session.active_branch_id,
        generation_id=expected_generation_id,
        sequence_number=max((m.sequence_number for m in transcript), default=0) + 1,
        round_number=target.round_number, exchange_number=0, role='user', message_kind='question',
        content=text, metadata={'interjection': True, 'interrupted_message_id': str(target.id)},
        created_at=max(at, session.updated_at))


def prepare_continuation(session: DebateSession, transcript: list[DebateMessage], *,
                         expected_generation_id: UUID, interjection_id: UUID,
                         idempotency_key: str, at: datetime,
                         max_attempts: int = 3,
                         ) -> tuple[DebateSession, DebateJob, DebateQueueMessage]:
    if session.status != 'interrupted_awaiting_user' or session.active_generation_id != expected_generation_id:
        raise DebateConcurrencyError('Debate is not waiting at this interruption')
    captured_at = session.created_at
    if session.analysis_context.captured_at:
        captured_at = min(captured_at, session.analysis_context.captured_at)
    if at < captured_at or at - captured_at > CONTINUATION_MAX_AGE:
        raise DebateConcurrencyError('Frozen discussion expired; start a new debate')
    target = interruption_target(transcript)
    point = next((m for m in transcript if m.id == interjection_id), None)
    if (point is None or point.role != 'user' or point.metadata.get('interjection') is not True
            or point.generation_id != expected_generation_id
            or point.metadata.get('interrupted_message_id') != str(target.id)
            or point.sequence_number <= target.sequence_number):
        raise DebateConcurrencyError('Continue requires an interjection at this interruption')
    round_number = target.round_number
    if round_number not in {1, 2}:
        raise DebateConcurrencyError('Invalid interruption round')
    # Keep one current point for the next provider request, not a hidden draft.
    if any(m.sequence_number > point.sequence_number for m in transcript):
        raise DebateConcurrencyError('Continue must use the latest interjection')
    stamp = max(at, session.updated_at)
    generation_id = uuid5(session.id, f'continue:{expected_generation_id}:{idempotency_key}')
    queued = DebateSession.model_validate({**session.model_dump(),
        'status': f'queued_round_{round_number}', 'active_generation_id': generation_id,
        'updated_at': stamp, 'completed_at': None})
    job = DebateJob(id=uuid5(session.id, f'continue-job:{idempotency_key}'), session_id=session.id,
        user_id=session.user_id, job_type=f'round_{round_number}',
        idempotency_key=f'continue:{session.id}:{expected_generation_id}:{interjection_id}:{idempotency_key}',
        max_attempts=max_attempts,
        available_at=stamp, created_at=stamp, updated_at=stamp)
    envelope = DebateQueueMessage(job_id=job.id, session_id=session.id, job_type=job.job_type,
        trace_id=f'trace_{job.id.hex}', enqueued_at=stamp)
    return queued, job, envelope
