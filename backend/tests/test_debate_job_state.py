from datetime import timedelta

import pytest

from app.services.debate_job_state import (
    DebateJobTransitionError,
    cancel_job,
    complete_job,
    fail_job,
    requeue_job,
    start_job,
)
from test_job_event_domain import NOW, build_job


def test_job_state_runs_and_completes_with_consistent_usage() -> None:
    queued = build_job()
    running = start_job(queued, at=NOW + timedelta(seconds=1))
    completed = complete_job(
        running,
        at=NOW + timedelta(seconds=2),
        provider_request_count=7,
        prompt_tokens=20,
        completion_tokens=30,
    )

    assert running.attempt_count == 1
    assert completed.status == "completed"
    assert completed.total_tokens == 50
    assert completed.provider_request_count == 7


def test_job_state_failure_uses_only_a_safe_error_code() -> None:
    failed = fail_job(
        build_job(),
        at=NOW + timedelta(seconds=1),
        safe_error_code="provider_unavailable",
    )

    assert failed.status == "failed"
    assert failed.safe_error_code == "provider_unavailable"
    with pytest.raises(DebateJobTransitionError, match="Only an active"):
        fail_job(
            failed,
            at=NOW + timedelta(seconds=2),
            safe_error_code="provider_unavailable",
        )


def test_job_state_cancellation_supports_queued_and_running_jobs() -> None:
    queued = build_job()
    cancelled_queued = cancel_job(queued, at=NOW + timedelta(seconds=1))
    running = start_job(queued, at=NOW + timedelta(seconds=1))
    cancelled_running = cancel_job(
        running,
        at=NOW + timedelta(seconds=2),
        provider_request_count=2,
        prompt_tokens=10,
        completion_tokens=5,
    )

    assert cancelled_queued.status == "cancelled"
    assert cancelled_queued.started_at is None
    assert cancelled_running.status == "cancelled"
    assert cancelled_running.provider_request_count == 2
    assert cancelled_running.total_tokens == 15
    with pytest.raises(DebateJobTransitionError, match="Only an active"):
        cancel_job(cancelled_running, at=NOW + timedelta(seconds=3))


def test_job_state_retry_preserves_attempt_and_cumulative_usage() -> None:
    running = start_job(build_job(), at=NOW + timedelta(seconds=1))
    retried = requeue_job(
        running,
        at=NOW + timedelta(seconds=2),
        provider_request_count=2,
        prompt_tokens=10,
        completion_tokens=5,
    )
    second_attempt = start_job(retried, at=NOW + timedelta(seconds=3))

    assert retried.status == "queued"
    assert retried.attempt_count == 1
    assert retried.started_at is None
    assert retried.provider_request_count == 2
    assert retried.total_tokens == 15
    assert second_attempt.attempt_count == 2


def test_job_state_retry_rejects_an_exhausted_attempt_budget() -> None:
    exhausted = start_job(
        build_job(max_attempts=1),
        at=NOW + timedelta(seconds=1),
    )

    with pytest.raises(DebateJobTransitionError, match="exhausted"):
        requeue_job(exhausted, at=NOW + timedelta(seconds=2))
