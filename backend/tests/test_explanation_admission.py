from __future__ import annotations

import pytest

from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.explanation_admission import (
    ExplanationAdmissionPolicy,
    ExplanationRateLimitExceeded,
)
from test_debate_domain import USER_ID


def build_policy(
    backend: LocalCacheBackend,
    *,
    rate_limit: int = 2,
) -> ExplanationAdmissionPolicy:
    return ExplanationAdmissionPolicy(
        ResilientCacheBackend(backend),
        rate_limit=rate_limit,
        rate_window_seconds=3600,
        clock=lambda: 3700.0,
    )


def test_explanation_admission_limits_a_hashed_user_key() -> None:
    backend = LocalCacheBackend()
    policy = build_policy(backend)

    first = policy.admit(USER_ID)
    second = policy.admit(USER_ID)

    assert first.rate_count == 1
    assert first.remaining == 1
    assert second.rate_count == 2
    assert second.remaining == 0
    rate_key = policy.rate_key(USER_ID, 1)
    assert rate_key.startswith("rate:explain:v1:")
    assert str(USER_ID) not in rate_key
    assert backend.get(rate_key) == "2"

    with pytest.raises(ExplanationRateLimitExceeded) as error:
        policy.admit(USER_ID)

    assert error.value.retry_after_seconds == 3500


def test_explanation_admission_validates_its_bounded_configuration() -> None:
    backend = LocalCacheBackend()

    with pytest.raises(ValueError, match="rate_limit"):
        ExplanationAdmissionPolicy(backend, rate_limit=0, rate_window_seconds=60)
    with pytest.raises(ValueError, match="rate_window_seconds"):
        ExplanationAdmissionPolicy(backend, rate_limit=1, rate_window_seconds=0)
