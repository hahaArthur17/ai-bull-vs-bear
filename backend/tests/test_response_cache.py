from __future__ import annotations

from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.response_cache import (
    JsonResponseCache,
    stock_bundle_cache_key,
    stock_search_cache_key,
)


def test_json_cache_reports_bypass_miss_and_hit() -> None:
    bypass = JsonResponseCache(ResilientCacheBackend(None), enabled=False)
    assert bypass.read("cache:key").status == "BYPASS"

    cache = JsonResponseCache(
        ResilientCacheBackend(LocalCacheBackend()),
        enabled=True,
    )
    first = cache.read("cache:key")
    cache.write("cache:key", {"ticker": "AAPL"}, ttl_seconds=30)
    second = cache.read("cache:key")

    assert first.status == "MISS"
    assert second.status == "HIT"
    assert second.value == {"ticker": "AAPL"}
    assert cache.metrics.snapshot() == {
        "HIT": 1,
        "MISS": 1,
        "BYPASS": 0,
        "DEGRADED": 0,
    }


def test_cache_keys_hash_queries_and_version_stock_bundles() -> None:
    search_key = stock_search_cache_key("  Private Question  ", 20)
    assert search_key.startswith("cache:stock-search:v1:")
    assert "private" not in search_key
    assert stock_search_cache_key("private   question", 20) == search_key
    assert stock_search_cache_key("private question", 10) != search_key

    assert stock_bundle_cache_key("aapl", clock=lambda: 601) == (
        "cache:stock-bundle:v1:AAPL:2"
    )
