from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from app.domain.base import AwareDatetime, ImmutableDomainModel


DebateJobType = Literal["round_1", "round_2", "explanation", "replay"]
DebateJobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]


class DebateJob(ImmutableDomainModel):
    id: UUID
    session_id: UUID
    user_id: UUID
    job_type: DebateJobType
    status: DebateJobStatus = "queued"
    idempotency_key: str = Field(min_length=8, max_length=200)
    queue_message_id: int | None = Field(default=None, gt=0)
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1, le=10)
    available_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    safe_error_code: str | None = Field(default=None, max_length=80)
    provider_request_count: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_job_lifecycle(self) -> DebateJob:
        if self.attempt_count > self.max_attempts:
            raise ValueError("Job attempts cannot exceed max_attempts")
        if self.updated_at < self.created_at:
            raise ValueError("Job updated_at cannot precede created_at")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("Job total_tokens must equal prompt plus completion tokens")
        if self.status == "running":
            if self.started_at is None or self.finished_at is not None:
                raise ValueError("A running job requires started_at and no finished_at")
            if self.attempt_count < 1:
                raise ValueError("A running job requires at least one attempt")
        terminal = self.status in {"completed", "failed", "cancelled"}
        if terminal != (self.finished_at is not None):
            raise ValueError("Only terminal jobs require finished_at")
        if self.status == "completed" and self.started_at is None:
            raise ValueError("A completed job requires started_at")
        if self.status == "failed" and not self.safe_error_code:
            raise ValueError("A failed job requires a safe error code")
        if self.status != "failed" and self.safe_error_code is not None:
            raise ValueError("Only a failed job may expose a safe error code")
        return self


class DebateQueueMessage(ImmutableDomainModel):
    """Identifier-only payload stored in Supabase Queue/pgmq."""

    schema_version: Literal[1] = 1
    job_id: UUID
    session_id: UUID
    job_type: DebateJobType
    trace_id: str = Field(
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )
    enqueued_at: AwareDatetime


class ClaimedDebateQueueMessage(ImmutableDomainModel):
    queue_message_id: int = Field(gt=0)
    read_count: int = Field(ge=1)
    enqueued_at: AwareDatetime
    visibility_deadline: AwareDatetime
    payload: DebateQueueMessage

    @model_validator(mode="after")
    def validate_visibility_window(self) -> ClaimedDebateQueueMessage:
        if self.visibility_deadline < self.enqueued_at:
            raise ValueError("Queue visibility deadline cannot precede enqueue time")
        return self
