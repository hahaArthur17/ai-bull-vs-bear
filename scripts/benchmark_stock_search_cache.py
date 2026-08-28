#!/usr/bin/env python3
"""Measure stock-search cache latency and avoided repository calls locally."""

from __future__ import annotations

import argparse
from math import ceil
import json
import platform
from statistics import median
from time import perf_counter_ns, sleep

from fastapi.testclient import TestClient

from app import main
from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.demo_store import DemoStore
from app.services.response_cache import JsonResponseCache


class DelayedCountingStore(DemoStore):
    def __init__(self, *, delay_seconds: float) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds
        self.list_stock_calls = 0

    def list_stocks(
        self,
        query: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        self.list_stock_calls += 1
        if self.delay_seconds:
            sleep(self.delay_seconds)
        return super().list_stocks(query, limit)


def percentile_95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, ceil(len(ordered) * 0.95) - 1)]


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "median_ms": round(median(values), 3),
        "p95_ms": round(percentile_95(values), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


def timed_stock_search(client: TestClient) -> tuple[float, str, object]:
    started = perf_counter_ns()
    response = client.get("/stocks", params={"q": "aapl", "limit": 20})
    elapsed_ms = (perf_counter_ns() - started) / 1_000_000
    if response.status_code != 200:
        raise RuntimeError(f"Stock search returned HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, list) or [item.get("ticker") for item in payload] != [
        "AAPL"
    ]:
        raise RuntimeError("Stock search returned an unexpected payload")
    return elapsed_ms, response.headers["x-cache-status"], payload


def run_scenario(
    client: TestClient,
    *,
    cache_enabled: bool,
    iterations: int,
    repository_delay_seconds: float,
) -> dict[str, object]:
    store = DelayedCountingStore(delay_seconds=repository_delay_seconds)
    cache = JsonResponseCache(
        ResilientCacheBackend(LocalCacheBackend()),
        enabled=cache_enabled,
    )
    previous_store = main.store
    previous_cache = main.response_cache
    timings: list[float] = []
    statuses: list[str] = []
    payloads: list[object] = []
    try:
        main.store = store
        main.response_cache = cache
        for _ in range(iterations):
            elapsed_ms, cache_status, payload = timed_stock_search(client)
            timings.append(elapsed_ms)
            statuses.append(cache_status)
            payloads.append(payload)
    finally:
        main.store = previous_store
        main.response_cache = previous_cache

    if any(payload != payloads[0] for payload in payloads[1:]):
        raise RuntimeError("Benchmark payload changed between iterations")
    if cache_enabled:
        if statuses[0] != "MISS" or any(status != "HIT" for status in statuses[1:]):
            raise RuntimeError(f"Unexpected enabled-cache statuses: {statuses}")
        measured_timings = timings[1:]
    else:
        if any(status != "BYPASS" for status in statuses):
            raise RuntimeError(f"Unexpected disabled-cache statuses: {statuses}")
        measured_timings = timings

    return {
        "requests": iterations,
        "repository_calls": store.list_stock_calls,
        "cache_status_counts": {
            status: statuses.count(status)
            for status in ("BYPASS", "MISS", "HIT", "DEGRADED")
        },
        "cold_miss_ms": round(timings[0], 3) if cache_enabled else None,
        "measured": summarize(measured_timings),
    }


def benchmark(*, iterations: int, repository_delay_ms: float) -> dict[str, object]:
    client = TestClient(main.app)
    client.get("/health")
    delay_seconds = repository_delay_ms / 1000
    uncached = run_scenario(
        client,
        cache_enabled=False,
        iterations=iterations,
        repository_delay_seconds=delay_seconds,
    )
    cached = run_scenario(
        client,
        cache_enabled=True,
        iterations=iterations,
        repository_delay_seconds=delay_seconds,
    )
    uncached_median = float(uncached["measured"]["median_ms"])  # type: ignore[index]
    cached_median = float(cached["measured"]["median_ms"])  # type: ignore[index]
    uncached_calls = int(uncached["repository_calls"])
    cached_calls = int(cached["repository_calls"])
    return {
        "benchmark": "stock-search-cache-v1",
        "endpoint": "GET /stocks?q=aapl&limit=20",
        "environment": {
            "transport": "FastAPI TestClient in-process",
            "persistence": "DemoStore with controlled delay",
            "cache": "LocalCacheBackend",
            "python": platform.python_version(),
            "iterations": iterations,
            "repository_delay_ms": repository_delay_ms,
        },
        "uncached": uncached,
        "cached": cached,
        "effect": {
            "hit_median_speedup_x": round(uncached_median / cached_median, 2),
            "repository_calls_avoided": uncached_calls - cached_calls,
            "repository_call_reduction_percent": round(
                (uncached_calls - cached_calls) / uncached_calls * 100,
                1,
            ),
        },
    }


def main_cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--repository-delay-ms", type=float, default=5.0)
    args = parser.parse_args()
    if args.iterations < 3:
        parser.error("--iterations must be at least 3")
    if args.repository_delay_ms < 0:
        parser.error("--repository-delay-ms cannot be negative")
    print(
        json.dumps(
            benchmark(
                iterations=args.iterations,
                repository_delay_ms=args.repository_delay_ms,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main_cli()
