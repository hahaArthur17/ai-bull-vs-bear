from __future__ import annotations

import pytest

from app.services.analysis_context import build_analysis_context
from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.response_cache import (
    JsonResponseCache,
    standard_debate_snapshot_cache_key,
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


def test_standard_debate_key_is_snapshot_bound_and_rejects_private_context() -> None:
    standard = build_analysis_context("AAPL", as_of="2026-08-28")
    contract = {"providers": [{"name": "technical", "version": "1"}]}
    key = standard_debate_snapshot_cache_key(
        standard,
        provider_contract=contract,
    )

    assert key.startswith("cache:standard-debate:v1:")
    assert "AAPL" not in key
    assert standard_debate_snapshot_cache_key(
        standard,
        provider_contract=contract,
    ) == key
    assert standard_debate_snapshot_cache_key(
        build_analysis_context("AAPL", as_of="2026-08-29"),
        provider_contract=contract,
    ) != key
    assert standard_debate_snapshot_cache_key(
        standard,
        provider_contract={"providers": [{"name": "technical", "version": "2"}]},
    ) != key

    with pytest.raises(ValueError, match="standard Debate context"):
        standard_debate_snapshot_cache_key(
            build_analysis_context(
                "AAPL",
                as_of="2026-08-28",
                question="My private question",
            ),
            provider_contract=contract,
        )
