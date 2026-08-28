from __future__ import annotations

import pytest

from app.config import Settings
from app.services.cache import (
    LocalCacheBackend,
    RedisCacheBackend,
    ResilientCacheBackend,
)


class BrokenBackend(LocalCacheBackend):
    def get(self, key: str) -> str | None:
        raise TimeoutError("private endpoint detail")

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        raise TimeoutError("private endpoint detail")


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.calls: list[tuple[object, ...]] = []

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: str, **options: object):
        self.calls.append(("set", key, value, options))
        if options.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    def delete(self, key: str):
        return int(self.values.pop(key, None) is not None)

    def eval(self, script: str, key_count: int, key: str, value: object):
        self.calls.append(("eval", script, key_count, key, value))
        if "redis.call('get'" in script:
            if self.values.get(key) == value:
                return self.delete(key)
            return 0
        count = int(self.values.get(key, "0")) + 1
        self.values[key] = str(count)
        return count

    def ping(self):
        return True


def test_local_cache_expires_values_locks_and_counters() -> None:
    now = [10.0]
    backend = LocalCacheBackend(clock=lambda: now[0])

    backend.set("cache:key", "value", ttl_seconds=5)
    assert backend.get("cache:key") == "value"
    assert backend.acquire_lock("lock:key", "owner-a", ttl_seconds=5) is True
    assert backend.acquire_lock("lock:key", "owner-b", ttl_seconds=5) is False
    assert backend.release_lock("lock:key", "owner-b") is False
    assert backend.release_lock("lock:key", "owner-a") is True
    assert backend.increment_with_expiry("rate:key", ttl_seconds=5) == 1
    assert backend.increment_with_expiry("rate:key", ttl_seconds=5) == 2

    now[0] = 16.0
    assert backend.get("cache:key") is None
    assert backend.increment_with_expiry("rate:key", ttl_seconds=5) == 1


def test_redis_adapter_uses_atomic_owner_lock_and_expiring_increment() -> None:
    client = FakeRedisClient()
    backend = RedisCacheBackend(client)

    assert backend.acquire_lock("lock:key", "owner-a", ttl_seconds=20) is True
    assert backend.acquire_lock("lock:key", "owner-b", ttl_seconds=20) is False
    assert backend.release_lock("lock:key", "owner-b") is False
    assert backend.release_lock("lock:key", "owner-a") is True
    assert backend.increment_with_expiry("rate:key", ttl_seconds=60) == 1
    assert backend.increment_with_expiry("rate:key", ttl_seconds=60) == 2
    assert backend.ping() is True
    assert any(call[0] == "eval" and "expire" in str(call[1]) for call in client.calls)


def test_redis_failure_degrades_without_leaking_key_or_exception_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    backend = ResilientCacheBackend(BrokenBackend())

    backend.set("private:user@example.com", "safe-value", ttl_seconds=30)
    assert backend.get("private:user@example.com") == "safe-value"
    health = backend.health()

    assert health.mode == "degraded"
    assert health.redis_configured is True
    assert health.degraded_operations == 2
    assert "private:user@example.com" not in caplog.text
    assert "private endpoint detail" not in caplog.text
    assert "TimeoutError" in caplog.text


def test_redis_configuration_is_explicit_and_url_scheme_is_validated() -> None:
    defaults = Settings(redis_enabled=False)
    assert defaults.redis_enabled is False
    assert defaults.debate_rate_limit_per_window == 3
    assert defaults.debate_rate_limit_window_seconds == 3600
    assert defaults.debate_active_ttl_seconds == 1200
    assert defaults.debate_idempotency_lock_ttl_seconds == 120
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings(redis_enabled=True)
    with pytest.raises(ValueError, match="redis:// or rediss://"):
        Settings(redis_enabled=True, redis_url="https://example.test")
    configured = Settings(
        _env_file=None,
        redis_enabled=True,
        redis_url="rediss://credential@example.test:6379",
    )
    represented_fields = {name for name, _value in configured.__repr_args__()}
    assert "redis_url" not in represented_fields
    assert "supabase_secret_key" not in represented_fields
    assert "groq_api_key" not in represented_fields
