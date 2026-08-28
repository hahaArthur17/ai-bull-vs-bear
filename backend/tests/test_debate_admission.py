from __future__ import annotations

from datetime import timedelta

import pytest

from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.debate_admission import (
    ActiveDebateExists,
    DebateAdmissionPolicy,
    DebateRateLimitExceeded,
)
from app.services.debate_state import request_session_cancellation, transition_session
from test_debate_domain import NOW, USER_ID
from test_debate_orchestrator import build_queued_round_one


def build_policy(
    backend: LocalCacheBackend,
    *,
    rate_limit: int = 3,
) -> DebateAdmissionPolicy:
    return DebateAdmissionPolicy(
        ResilientCacheBackend(backend),
        rate_limit=rate_limit,
        rate_window_seconds=3600,
        active_ttl_seconds=1200,
        clock=lambda: 3700.0,
    )


def test_active_reservation_is_atomic_and_user_keys_are_hashed() -> None:
    backend = LocalCacheBackend()
    repository = InMemoryDebateRepository()
    first_policy = build_policy(backend)
    second_policy = build_policy(backend)

    reservation = first_policy.reserve(USER_ID, repository)

    assert str(USER_ID) not in reservation.active_key
    assert str(USER_ID) not in first_policy.rate_key(USER_ID, 1)
    with pytest.raises(ActiveDebateExists):
        second_policy.reserve(USER_ID, repository)

    first_policy.release(reservation)
    next_reservation = second_policy.reserve(USER_ID, repository)
    assert next_reservation.rate_count == 2


def test_canonical_active_session_wins_and_terminal_cache_entry_is_recovered() -> None:
    backend = LocalCacheBackend()
    repository = InMemoryDebateRepository()
    policy = build_policy(backend)
    queued, _job = build_queued_round_one()
    repository.create_session(queued)

    with pytest.raises(ActiveDebateExists):
        policy.reserve(queued.user_id, repository)

    requested, _generation = request_session_cancellation(
        queued,
        at=NOW + timedelta(seconds=2),
    )
    requested = repository.update_session(requested, expected_status="queued_round_1")
    cancelled = transition_session(
        requested,
        "cancelled",
        at=NOW + timedelta(seconds=3),
    )
    repository.update_session(cancelled, expected_status="cancel_requested")

    reservation = policy.reserve(queued.user_id, repository)
    assert reservation.rate_count == 1


def test_rate_limit_releases_active_reservation_and_returns_bounded_retry() -> None:
    backend = LocalCacheBackend()
    repository = InMemoryDebateRepository()
    policy = build_policy(backend, rate_limit=2)

    first = policy.reserve(USER_ID, repository)
    policy.release(first)
    second = policy.reserve(USER_ID, repository)
    policy.release(second)

    with pytest.raises(DebateRateLimitExceeded) as error:
        policy.reserve(USER_ID, repository)

    assert error.value.retry_after_seconds == 3500
    assert backend.get(policy.active_key(USER_ID)) is None
