from __future__ import annotations

from app.domain.base import AwareDatetime
from app.domain.jobs import DebateJob


class DebateJobTransitionError(ValueError):
    """Raised when a job lifecycle change would violate canonical state."""


def start_job(job: DebateJob, *, at: AwareDatetime) -> DebateJob:
    if job.status != "queued":
        raise DebateJobTransitionError("Only a queued Debate job can start")
    if at < job.updated_at:
        raise DebateJobTransitionError("Job start time cannot precede its current state")
    if job.attempt_count >= job.max_attempts:
        raise DebateJobTransitionError("Debate job has exhausted its attempts")
    return _updated(
        job,
        status="running",
        attempt_count=job.attempt_count + 1,
        started_at=at,
        finished_at=None,
        safe_error_code=None,
        updated_at=at,
    )


def complete_job(
    job: DebateJob,
    *,
    at: AwareDatetime,
    provider_request_count: int,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> DebateJob:
    if job.status != "running":
        raise DebateJobTransitionError("Only a running Debate job can complete")
    if at < job.updated_at:
        raise DebateJobTransitionError("Job completion time cannot precede its current state")
    return _updated(
        job,
        status="completed",
        finished_at=at,
        safe_error_code=None,
        provider_request_count=provider_request_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        updated_at=at,
    )


def fail_job(
    job: DebateJob,
    *,
    at: AwareDatetime,
    safe_error_code: str,
    provider_request_count: int = 0,
) -> DebateJob:
    if job.status not in {"queued", "running"}:
        raise DebateJobTransitionError("Only an active Debate job can fail")
    if at < job.updated_at:
        raise DebateJobTransitionError("Job failure time cannot precede its current state")
    if not safe_error_code:
        raise DebateJobTransitionError("A failed Debate job requires a safe error code")
    return _updated(
        job,
        status="failed",
        finished_at=at,
        safe_error_code=safe_error_code,
        provider_request_count=provider_request_count,
        updated_at=at,
    )


def cancel_job(
    job: DebateJob,
    *,
    at: AwareDatetime,
    provider_request_count: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> DebateJob:
    if job.status not in {"queued", "running"}:
        raise DebateJobTransitionError("Only an active Debate job can be cancelled")
    if at < job.updated_at:
        raise DebateJobTransitionError("Job cancellation time cannot precede its current state")

    requests = max(job.provider_request_count, provider_request_count or 0)
    prompts = max(job.prompt_tokens, prompt_tokens or 0)
    completions = max(job.completion_tokens, completion_tokens or 0)
    return _updated(
        job,
        status="cancelled",
        finished_at=at,
        safe_error_code=None,
        provider_request_count=requests,
        prompt_tokens=prompts,
        completion_tokens=completions,
        total_tokens=prompts + completions,
        updated_at=at,
    )


def _updated(job: DebateJob, **changes: object) -> DebateJob:
    return DebateJob.model_validate({**job.model_dump(mode="python"), **changes})
