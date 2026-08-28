from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from threading import RLock
from time import time
from typing import Callable, Literal

from app.domain.factors import AnalysisContext
from app.services.cache import ResilientCacheBackend


CacheStatus = Literal["HIT", "MISS", "BYPASS", "DEGRADED"]


@dataclass(frozen=True)
class CacheRead:
    status: CacheStatus
    value: object | None


class CacheMetrics:
    def __init__(self) -> None:
        self._counts: dict[CacheStatus, int] = {
            "HIT": 0,
            "MISS": 0,
            "BYPASS": 0,
            "DEGRADED": 0,
        }
        self._mutex = RLock()

    def record(self, status: CacheStatus) -> None:
        with self._mutex:
            self._counts[status] += 1

    def snapshot(self) -> dict[CacheStatus, int]:
        with self._mutex:
            return self._counts.copy()


class JsonResponseCache:
    """Caches bounded JSON-compatible API payloads without caching user text."""

    def __init__(
        self,
        backend: ResilientCacheBackend,
        *,
        enabled: bool,
        metrics: CacheMetrics | None = None,
    ) -> None:
        self.backend = backend
        self.enabled = enabled
        self.metrics = metrics or CacheMetrics()

    def read(self, key: str) -> CacheRead:
        if not self.enabled:
            return self.bypass()
        raw = self.backend.get(key)
        degraded = self.backend.mode == "degraded"
        if raw is None:
            result = CacheRead(status="DEGRADED" if degraded else "MISS", value=None)
            self.metrics.record(result.status)
            return result
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            self.backend.delete(key)
            result = CacheRead(status="DEGRADED" if degraded else "MISS", value=None)
            self.metrics.record(result.status)
            return result
        result = CacheRead(status="DEGRADED" if degraded else "HIT", value=value)
        self.metrics.record(result.status)
        return result

    def bypass(self) -> CacheRead:
        result = CacheRead(status="BYPASS", value=None)
        self.metrics.record(result.status)
        return result

    def write(self, key: str, value: object, *, ttl_seconds: int) -> None:
        if not self.enabled:
            return
        payload = json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        self.backend.set(key, payload, ttl_seconds=ttl_seconds)

    def response_status(self, read_status: CacheStatus) -> CacheStatus:
        return "DEGRADED" if self.backend.mode == "degraded" else read_status


def stock_search_cache_key(query: str | None, limit: int) -> str:
    normalized = " ".join((query or "").strip().lower().split())
    digest = sha256(f"{normalized}|{limit}".encode("utf-8")).hexdigest()
    return f"cache:stock-search:v1:{digest}"


def stock_bundle_cache_key(
    ticker: str,
    *,
    clock: Callable[[], float] = time,
    version_seconds: int = 300,
) -> str:
    if version_seconds < 1:
        raise ValueError("version_seconds must be at least 1")
    normalized = ticker.strip().upper()
    if not normalized or not normalized.replace(".", "").replace("-", "").isalnum():
        raise ValueError("ticker is invalid")
    data_version = int(clock() // version_seconds)
    return f"cache:stock-bundle:v1:{normalized}:{data_version}"


def standard_debate_snapshot_cache_key(
    context: AnalysisContext,
    *,
    provider_contract: object,
) -> str:
    if context.question is not None or context.metadata:
        raise ValueError("only a standard Debate context can use the shared cache")
    payload = json.dumps(
        {
            "context": context.model_dump(
                mode="json",
                exclude={"question", "metadata"},
            ),
            "provider_contract": provider_contract,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()
    return f"cache:standard-debate:v1:{digest}"
