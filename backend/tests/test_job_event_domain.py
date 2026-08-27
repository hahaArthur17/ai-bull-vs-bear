from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.events import DebateEvent
from app.domain.jobs import DebateJob, DebateQueueMessage


NOW = datetime(2026, 8, 27, 11, 0, tzinfo=timezone.utc)
JOB_ID = UUID("00000000-0000-4000-8000-000000000030")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000031")
USER_ID = UUID("00000000-0000-4000-8000-000000000032")


def build_job(**updates: object) -> DebateJob:
    payload = {
        "id": JOB_ID,
        "session_id": SESSION_ID,
        "user_id": USER_ID,
        "job_type": "round_1",
        "status": "queued",
        "idempotency_key": "round-1:session-id:branch-id",
        "available_at": NOW,
        "created_at": NOW,
        "updated_at": NOW,
        **updates,
    }
    return DebateJob.model_validate(payload)


def test_job_ledger_validates_attempts_terminal_state_and_token_totals() -> None:
    running = build_job(status="running", attempt_count=1, started_at=NOW)
    completed = build_job(
        status="completed",
        attempt_count=1,
        started_at=NOW,
        finished_at=NOW,
        provider_request_count=7,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
    )

    assert running.status == "running"
    assert completed.total_tokens == 150
    with pytest.raises(ValidationError, match="total_tokens"):
        build_job(prompt_tokens=10, completion_tokens=5, total_tokens=20)


def test_failed_job_requires_a_safe_code_and_finished_timestamp() -> None:
    with pytest.raises(ValidationError, match="finished_at"):
        build_job(status="failed", attempt_count=3, safe_error_code="provider_unavailable")

    failed = build_job(
        status="failed",
        attempt_count=3,
        finished_at=NOW,
        safe_error_code="provider_unavailable",
    )

    assert failed.safe_error_code == "provider_unavailable"


def test_queue_message_accepts_identifiers_only() -> None:
    message = DebateQueueMessage(
        job_id=JOB_ID,
        session_id=SESSION_ID,
        job_type="round_1",
        trace_id="trace_20260827_001",
        enqueued_at=NOW,
    )

    assert set(message.model_dump(mode="json")) == {
        "schema_version",
        "job_id",
        "session_id",
        "job_type",
        "trace_id",
        "enqueued_at",
    }
    with pytest.raises(ValidationError, match="extra_forbidden"):
        DebateQueueMessage.model_validate(
            {**message.model_dump(mode="python"), "authorization": "Bearer secret"}
        )


def test_event_envelope_is_versioned_json_safe_and_round_trippable() -> None:
    event = DebateEvent(
        event_id=UUID("00000000-0000-4000-8000-000000000033"),
        session_id=SESSION_ID,
        sequence=12,
        type="turn.delta",
        timestamp=NOW,
        payload={"generation_id": "generation-1", "delta": "bounded text"},
    )

    assert DebateEvent.model_validate_json(event.model_dump_json()) == event
    assert event.version == 1


def test_event_delta_payload_preserves_meaningful_boundary_whitespace() -> None:
    event = DebateEvent(
        event_id=UUID("00000000-0000-4000-8000-000000000035"),
        session_id=SESSION_ID,
        sequence=13,
        type="turn.delta",
        timestamp=NOW,
        payload={"delta": " leading and trailing "},
    )

    assert event.payload["delta"] == " leading and trailing "


def test_event_payload_rejects_nested_sensitive_keys() -> None:
    with pytest.raises(ValidationError, match="forbidden sensitive key"):
        DebateEvent(
            event_id=UUID("00000000-0000-4000-8000-000000000034"),
            session_id=SESSION_ID,
            sequence=1,
            type="session.created",
            timestamp=NOW,
            payload={"debug": {"access-token": "must-not-leak"}},
        )


def test_domain_timestamps_must_include_a_timezone() -> None:
    with pytest.raises(ValidationError, match="include a timezone"):
        DebateQueueMessage(
            job_id=JOB_ID,
            session_id=SESSION_ID,
            job_type="round_1",
            trace_id="trace_20260827_001",
            enqueued_at=datetime(2026, 8, 27, 11, 0),
        )
