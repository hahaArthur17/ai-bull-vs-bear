from datetime import timedelta

import pytest

from app.services.debate_job_state import (
    DebateJobTransitionError,
    complete_job,
    fail_job,
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
