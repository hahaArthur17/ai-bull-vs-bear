from __future__ import annotations

from collections.abc import Mapping
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, JsonValue, model_validator

from app.domain.base import AwareDatetime, ImmutableDomainModel


DebateEventType = Literal[
    "session.created",
    "job.queued",
    "job.started",
    "job.retry_scheduled",
    "job.failed",
    "turn.started",
    "turn.delta",
    "turn.citation",
    "turn.completed",
    "judge.started",
    "judge.delta",
    "judge.completed",
    "session.awaiting_user",
    "explanation.started",
    "explanation.delta",
    "explanation.completed",
    "session.cancel_requested",
    "session.cancelled",
    "session.completed",
    "session.failed",
    "heartbeat",
]


_FORBIDDEN_PAYLOAD_KEYS = {
    "authorization",
    "access_token",
    "refresh_token",
    "api_key",
    "provider_key",
    "service_role_key",
    "jwt",
    "secret",
}


def _contains_forbidden_key(value: JsonValue) -> bool:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in _FORBIDDEN_PAYLOAD_KEYS or _contains_forbidden_key(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


class DebateEvent(ImmutableDomainModel):
    # Provider deltas may begin or end with meaningful whitespace. Preserve
    # nested payload strings exactly so streamed text can be reconstructed.
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=False,
        allow_inf_nan=False,
    )

    version: Literal[1] = 1
    event_id: UUID
    session_id: UUID
    sequence: int = Field(ge=0)
    type: DebateEventType
    timestamp: AwareDatetime
    payload: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def reject_sensitive_payload_keys(self) -> DebateEvent:
        if _contains_forbidden_key(self.payload):
            raise ValueError("Event payload contains a forbidden sensitive key")
        return self
