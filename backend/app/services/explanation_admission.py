from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import time
from typing import Callable
from uuid import UUID

from app.services.cache import CacheBackend


class ExplanationRateLimitExceeded(RuntimeError):
    """An explanation request exceeded its bounded user admission window."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Explanation rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class ExplanationAdmission:
    rate_count: int
    rate_limit: int

    @property
    def remaining(self) -> int:
        return max(0, self.rate_limit - self.rate_count)


class ExplanationAdmissionPolicy:
    """Limit per-user explanation work without making cache state canonical."""

    def __init__(
        self,
        backend: CacheBackend,
        *,
        rate_limit: int,
        rate_window_seconds: int,
        clock: Callable[[], float] = time,
    ) -> None:
        if rate_limit < 1:
            raise ValueError("rate_limit must be at least 1")
        if rate_window_seconds < 1:
            raise ValueError("rate_window_seconds must be at least 1")
        self.backend = backend
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self.clock = clock

    def admit(self, user_id: UUID) -> ExplanationAdmission:
        now = self.clock()
        window = int(now // self.rate_window_seconds)
        rate_count = self.backend.increment_with_expiry(
            self.rate_key(user_id, window),
            ttl_seconds=self.rate_window_seconds,
        )
        if rate_count > self.rate_limit:
            remaining_window = self.rate_window_seconds - int(now % self.rate_window_seconds)
            raise ExplanationRateLimitExceeded(max(1, remaining_window))
        return ExplanationAdmission(rate_count=rate_count, rate_limit=self.rate_limit)

    @staticmethod
    def _user_hash(user_id: UUID) -> str:
        return sha256(str(user_id).encode("utf-8")).hexdigest()

    def rate_key(self, user_id: UUID, window: int) -> str:
        return f"rate:explain:v1:{self._user_hash(user_id)}:{window}"
