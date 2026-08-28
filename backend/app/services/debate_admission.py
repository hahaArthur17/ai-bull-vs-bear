from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import time
from typing import Callable
from uuid import UUID, uuid4

from app.domain.debate import DebateSession
from app.repositories.debate_repository import DebateUnitOfWork
from app.services.cache import CacheBackend


TERMINAL_SESSION_STATUSES = frozenset({"completed", "cancelled", "failed"})


class DebateAdmissionError(RuntimeError):
    """A new Debate cannot be admitted under the configured policy."""


class ActiveDebateExists(DebateAdmissionError):
    """The user already owns a canonical non-terminal Debate."""


class DebateRateLimitExceeded(DebateAdmissionError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Debate generation rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class DebateAdmissionReservation:
    user_id: UUID
    active_key: str
    owner: str
    rate_count: int
    rate_limit: int

    @property
    def remaining(self) -> int:
        return max(0, self.rate_limit - self.rate_count)


class DebateAdmissionPolicy:
    """Bound new Debate work by user without making cache state canonical."""

    def __init__(
        self,
        backend: CacheBackend,
        *,
        rate_limit: int,
        rate_window_seconds: int,
        active_ttl_seconds: int,
        clock: Callable[[], float] = time,
    ) -> None:
        if rate_limit < 1:
            raise ValueError("rate_limit must be at least 1")
        if rate_window_seconds < 1 or active_ttl_seconds < 1:
            raise ValueError("admission TTLs must be at least 1")
        self.backend = backend
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self.active_ttl_seconds = active_ttl_seconds
        self.clock = clock

    def reserve(
        self,
        user_id: UUID,
        repository: DebateUnitOfWork,
    ) -> DebateAdmissionReservation:
        active_key = self.active_key(user_id)
        canonical_active = self._canonical_active_session(user_id, repository)
        if canonical_active is not None:
            self.backend.set(
                active_key,
                str(canonical_active.id),
                ttl_seconds=self.active_ttl_seconds,
            )
            raise ActiveDebateExists("One active Debate is already in progress")

        cached_owner = self.backend.get(active_key)
        if cached_owner is not None:
            if self._cached_session_is_stale(cached_owner, user_id, repository):
                self.backend.delete(active_key)
            else:
                raise ActiveDebateExists("One active Debate is already being admitted")

        owner = f"reservation:{uuid4()}"
        if not self.backend.acquire_lock(
            active_key,
            owner,
            ttl_seconds=self.active_ttl_seconds,
        ):
            raise ActiveDebateExists("One active Debate is already being admitted")

        now = self.clock()
        window = int(now // self.rate_window_seconds)
        rate_count = self.backend.increment_with_expiry(
            self.rate_key(user_id, window),
            ttl_seconds=self.rate_window_seconds,
        )
        if rate_count > self.rate_limit:
            self.backend.release_lock(active_key, owner)
            remaining_window = self.rate_window_seconds - int(now % self.rate_window_seconds)
            raise DebateRateLimitExceeded(max(1, remaining_window))

        return DebateAdmissionReservation(
            user_id=user_id,
            active_key=active_key,
            owner=owner,
            rate_count=rate_count,
            rate_limit=self.rate_limit,
        )

    def confirm(
        self,
        reservation: DebateAdmissionReservation,
        session: DebateSession,
    ) -> None:
        if session.user_id != reservation.user_id:
            raise ValueError("admission reservation owner does not match the Session")
        self.backend.set(
            reservation.active_key,
            str(session.id),
            ttl_seconds=self.active_ttl_seconds,
        )

    def release(self, reservation: DebateAdmissionReservation) -> None:
        self.backend.release_lock(reservation.active_key, reservation.owner)

    @staticmethod
    def _user_hash(user_id: UUID) -> str:
        return sha256(str(user_id).encode("utf-8")).hexdigest()

    def active_key(self, user_id: UUID) -> str:
        return f"active-debate:v1:{self._user_hash(user_id)}"

    def rate_key(self, user_id: UUID, window: int) -> str:
        return f"rate:debate:v1:{self._user_hash(user_id)}:{window}"

    @staticmethod
    def _canonical_active_session(
        user_id: UUID,
        repository: DebateUnitOfWork,
    ) -> DebateSession | None:
        return next(
            (
                session
                for session in repository.list_sessions(user_id, limit=100)
                if session.status not in TERMINAL_SESSION_STATUSES
            ),
            None,
        )

    @staticmethod
    def _cached_session_is_stale(
        cached_owner: str,
        user_id: UUID,
        repository: DebateUnitOfWork,
    ) -> bool:
        try:
            session_id = UUID(cached_owner)
        except ValueError:
            return False
        session = repository.get_session(session_id, user_id)
        return session is None or session.status in TERMINAL_SESSION_STATUSES
