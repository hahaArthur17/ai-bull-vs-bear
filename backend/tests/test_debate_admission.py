from __future__ import annotations

from datetime import timedelta

import pytest

from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.debate_admission import (
    ActiveDebateExists,
    DebateIdempotencyGuard,
    DebateIdempotencyLockBusy,
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


def test_idempotency_lock_key_is_scoped_hashed_and_validated() -> None:
    guard = DebateIdempotencyGuard(LocalCacheBackend(), ttl_seconds=30)
    raw_key = "client-request-42"

    lock_key = guard.lock_key(USER_ID, raw_key)

    assert str(USER_ID) not in lock_key
    assert raw_key not in lock_key
    assert lock_key == guard.lock_key(USER_ID, raw_key)
    assert lock_key != guard.lock_key(USER_ID, "client-request-43")
    with pytest.raises(ValueError, match="cannot be blank"):
        guard.lock_key(USER_ID, "  ")
    with pytest.raises(ValueError, match="TTL must be at least 1"):
        DebateIdempotencyGuard(LocalCacheBackend(), ttl_seconds=0)


def test_idempotency_lock_is_atomic_and_owner_safe() -> None:
    backend = LocalCacheBackend()
    first_guard = DebateIdempotencyGuard(backend, ttl_seconds=30)
    second_guard = DebateIdempotencyGuard(backend, ttl_seconds=30)

    reservation = first_guard.acquire(USER_ID, "client-request-42")

    assert backend.release_lock(reservation.lock_key, "wrong-owner") is False
    with pytest.raises(DebateIdempotencyLockBusy):
        second_guard.acquire(USER_ID, "client-request-42")

    assert first_guard.release(reservation) is True
    assert second_guard.acquire(USER_ID, "client-request-42")


def test_idempotency_lock_recovers_after_ttl_expiry() -> None:
    now = [100.0]
    backend = LocalCacheBackend(clock=lambda: now[0])
    guard = DebateIdempotencyGuard(backend, ttl_seconds=10)

    first = guard.acquire(USER_ID, "client-request-42")
    now[0] += 10
    second = guard.acquire(USER_ID, "client-request-42")

    assert first.lock_key == second.lock_key
    assert first.owner != second.owner


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
