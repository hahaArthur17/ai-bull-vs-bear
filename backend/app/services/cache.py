from __future__ import annotations

from dataclasses import dataclass
import logging
from threading import RLock
from time import monotonic
from typing import Callable, Literal, Protocol


logger = logging.getLogger(__name__)

CacheBackendMode = Literal["local", "redis", "degraded"]


class CacheBackend(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None: ...

    def delete(self, key: str) -> None: ...

    def acquire_lock(self, key: str, owner: str, *, ttl_seconds: int) -> bool: ...

    def release_lock(self, key: str, owner: str) -> bool: ...

    def increment_with_expiry(self, key: str, *, ttl_seconds: int) -> int: ...

    def ping(self) -> bool: ...


@dataclass(frozen=True)
class CacheBackendHealth:
    mode: CacheBackendMode
    redis_configured: bool
    redis_reachable: bool | None
    degraded_operations: int


@dataclass
class _LocalValue:
    value: str
    expires_at: float


class LocalCacheBackend:
    """Thread-safe TTL cache and coordination fallback for one process."""

    def __init__(self, *, clock: Callable[[], float] = monotonic) -> None:
        self._clock = clock
        self._values: dict[str, _LocalValue] = {}
        self._mutex = RLock()

    def _live_value(self, key: str) -> _LocalValue | None:
        value = self._values.get(key)
        if value is not None and value.expires_at <= self._clock():
            self._values.pop(key, None)
            return None
        return value

    @staticmethod
    def _expiry(clock: Callable[[], float], ttl_seconds: int) -> float:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        return clock() + ttl_seconds

    def get(self, key: str) -> str | None:
        with self._mutex:
            value = self._live_value(key)
            return value.value if value is not None else None

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        with self._mutex:
            self._values[key] = _LocalValue(
                value=value,
                expires_at=self._expiry(self._clock, ttl_seconds),
            )

    def delete(self, key: str) -> None:
        with self._mutex:
            self._values.pop(key, None)

    def acquire_lock(self, key: str, owner: str, *, ttl_seconds: int) -> bool:
        if not owner:
            raise ValueError("lock owner cannot be blank")
        with self._mutex:
            if self._live_value(key) is not None:
                return False
            self._values[key] = _LocalValue(
                value=owner,
                expires_at=self._expiry(self._clock, ttl_seconds),
            )
            return True

    def release_lock(self, key: str, owner: str) -> bool:
        with self._mutex:
            value = self._live_value(key)
            if value is None or value.value != owner:
                return False
            self._values.pop(key, None)
            return True

    def increment_with_expiry(self, key: str, *, ttl_seconds: int) -> int:
        with self._mutex:
            value = self._live_value(key)
            if value is None:
                self._values[key] = _LocalValue(
                    value="1",
                    expires_at=self._expiry(self._clock, ttl_seconds),
                )
                return 1
            try:
                count = int(value.value) + 1
            except ValueError as exc:
                raise ValueError("counter value is not an integer") from exc
            value.value = str(count)
            return count

    def ping(self) -> bool:
        return True


class RedisCacheBackend:
    """Small redis-py adapter; the injected client keeps tests network-free."""

    _RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
""".strip()
    _INCREMENT_SCRIPT = """
local current = redis.call('incr', KEYS[1])
if current == 1 then
  redis.call('expire', KEYS[1], ARGV[1])
end
return current
""".strip()

    def __init__(self, client: object) -> None:
        self._client = client

    def get(self, key: str) -> str | None:
        value = self._client.get(key)  # type: ignore[attr-defined]
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        self._client.set(key, value, ex=ttl_seconds)  # type: ignore[attr-defined]

    def delete(self, key: str) -> None:
        self._client.delete(key)  # type: ignore[attr-defined]

    def acquire_lock(self, key: str, owner: str, *, ttl_seconds: int) -> bool:
        if not owner:
            raise ValueError("lock owner cannot be blank")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        return bool(
            self._client.set(key, owner, nx=True, ex=ttl_seconds)  # type: ignore[attr-defined]
        )

    def release_lock(self, key: str, owner: str) -> bool:
        result = self._client.eval(  # type: ignore[attr-defined]
            self._RELEASE_LOCK_SCRIPT,
            1,
            key,
            owner,
        )
        return bool(result)

    def increment_with_expiry(self, key: str, *, ttl_seconds: int) -> int:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        return int(
            self._client.eval(  # type: ignore[attr-defined]
                self._INCREMENT_SCRIPT,
                1,
                key,
                ttl_seconds,
            )
        )

    def ping(self) -> bool:
        return bool(self._client.ping())  # type: ignore[attr-defined]


class ResilientCacheBackend:
    """Uses Redis when configured and fails open to a bounded local backend."""

    def __init__(
        self,
        primary: CacheBackend | None,
        *,
        fallback: CacheBackend | None = None,
    ) -> None:
        self._primary = primary
        self._fallback = fallback or LocalCacheBackend()
        self._state_mutex = RLock()
        self._mode: CacheBackendMode = "redis" if primary is not None else "local"
        self._degraded_operations = 0

    @property
    def mode(self) -> CacheBackendMode:
        with self._state_mutex:
            return self._mode

    def _mark_success(self) -> None:
        if self._primary is None:
            return
        with self._state_mutex:
            self._mode = "redis"

    def _mark_degraded(self, exc: Exception) -> None:
        with self._state_mutex:
            self._mode = "degraded"
            self._degraded_operations += 1
        logger.warning("Redis operation degraded to local fallback: %s", type(exc).__name__)

    def _read(self, operation: str, *args: object, **kwargs: object):
        if self._primary is None:
            return getattr(self._fallback, operation)(*args, **kwargs)
        try:
            result = getattr(self._primary, operation)(*args, **kwargs)
            self._mark_success()
            return result
        except Exception as exc:
            self._mark_degraded(exc)
            return getattr(self._fallback, operation)(*args, **kwargs)

    def get(self, key: str) -> str | None:
        return self._read("get", key)

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        self._read("set", key, value, ttl_seconds=ttl_seconds)

    def delete(self, key: str) -> None:
        self._read("delete", key)

    def acquire_lock(self, key: str, owner: str, *, ttl_seconds: int) -> bool:
        return bool(self._read("acquire_lock", key, owner, ttl_seconds=ttl_seconds))

    def release_lock(self, key: str, owner: str) -> bool:
        return bool(self._read("release_lock", key, owner))

    def increment_with_expiry(self, key: str, *, ttl_seconds: int) -> int:
        return int(self._read("increment_with_expiry", key, ttl_seconds=ttl_seconds))

    def ping(self) -> bool:
        return bool(self._read("ping"))

    def health(self, *, probe: bool = False) -> CacheBackendHealth:
        reachable: bool | None = None
        if self._primary is not None and probe:
            try:
                reachable = self._primary.ping()
                self._mark_success()
            except Exception as exc:
                reachable = False
                self._mark_degraded(exc)
        with self._state_mutex:
            return CacheBackendHealth(
                mode=self._mode,
                redis_configured=self._primary is not None,
                redis_reachable=reachable,
                degraded_operations=self._degraded_operations,
            )


def build_cache_backend(
    *,
    enabled: bool,
    redis_url: str | None,
    connect_timeout_seconds: float,
    socket_timeout_seconds: float,
) -> ResilientCacheBackend:
    if not enabled:
        return ResilientCacheBackend(None)
    if not redis_url:
        raise ValueError("REDIS_URL is required when Redis is enabled")
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - deployment dependency guard
        raise RuntimeError("Redis support package is unavailable") from exc
    client = redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=connect_timeout_seconds,
        socket_timeout=socket_timeout_seconds,
        health_check_interval=30,
    )
    return ResilientCacheBackend(RedisCacheBackend(client))
