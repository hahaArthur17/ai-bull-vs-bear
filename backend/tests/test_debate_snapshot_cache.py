from __future__ import annotations

from app.domain.factors import AnalysisContext, FactorProviderFailure, FactorSnapshot
from app.services.analysis_context import build_analysis_context
from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.debate_snapshot_cache import StandardDebateSnapshotCache
from app.services.response_cache import (
    JsonResponseCache,
    standard_debate_snapshot_cache_key,
)


PROVIDER_CONTRACT = {"providers": [], "expected_categories": []}


class RecordingBackend(LocalCacheBackend):
    def __init__(self) -> None:
        super().__init__()
        self.writes: list[tuple[str, str]] = []

    def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        self.writes.append((key, value))
        super().set(key, value, ttl_seconds=ttl_seconds)


def _snapshot(context: AnalysisContext) -> FactorSnapshot:
    return FactorSnapshot(ticker=context.ticker, as_of=context.as_of)


def test_standard_snapshot_is_reused_without_sharing_canonical_user_state() -> None:
    calls: list[AnalysisContext] = []
    cache = StandardDebateSnapshotCache(
        JsonResponseCache(
            ResilientCacheBackend(LocalCacheBackend()),
            enabled=True,
        )
    )
    context = build_analysis_context("AAPL", as_of="2026-08-28")

    def collect(value: AnalysisContext) -> FactorSnapshot:
        calls.append(value)
        return _snapshot(value)

    first = cache.get_or_collect(
        context,
        collect,
        provider_contract=PROVIDER_CONTRACT,
    )
    second = cache.get_or_collect(
        context,
        collect,
        provider_contract=PROVIDER_CONTRACT,
    )

    assert first.status == "MISS"
    assert second.status == "HIT"
    assert second.snapshot == first.snapshot
    assert calls == [context]


def test_custom_question_and_top_level_metadata_always_bypass_shared_cache() -> None:
    calls: list[AnalysisContext] = []
    backend = RecordingBackend()
    response_cache = JsonResponseCache(
        ResilientCacheBackend(backend),
        enabled=True,
    )
    cache = StandardDebateSnapshotCache(response_cache)

    def collect(value: AnalysisContext) -> FactorSnapshot:
        calls.append(value)
        return _snapshot(value)

    private_question = build_analysis_context(
        "AAPL",
        as_of="2026-08-28",
        question="My private question",
    )
    private_metadata = private_question.model_copy(
        update={"question": None, "metadata": {"user_id": "private-user"}}
    )

    assert cache.get_or_collect(
        private_question,
        collect,
        provider_contract=PROVIDER_CONTRACT,
    ).status == "BYPASS"
    assert cache.get_or_collect(
        private_question,
        collect,
        provider_contract=PROVIDER_CONTRACT,
    ).status == "BYPASS"
    assert cache.get_or_collect(
        private_metadata,
        collect,
        provider_contract=PROVIDER_CONTRACT,
    ).status == "BYPASS"
    assert len(calls) == 3
    assert response_cache.metrics.snapshot()["BYPASS"] == 3
    assert backend.writes == []


def test_invalid_cached_snapshot_is_recollected_from_canonical_context() -> None:
    backend = LocalCacheBackend()
    response_cache = JsonResponseCache(
        ResilientCacheBackend(backend),
        enabled=True,
    )
    cache = StandardDebateSnapshotCache(response_cache)
    context = build_analysis_context("AAPL", as_of="2026-08-28")

    first = cache.get_or_collect(
        context,
        _snapshot,
        provider_contract=PROVIDER_CONTRACT,
    )
    assert first.status == "MISS"
    key = standard_debate_snapshot_cache_key(
        context,
        provider_contract=PROVIDER_CONTRACT,
    )
    backend.set(
        key,
        FactorSnapshot(ticker="GOOG", as_of=context.as_of).model_dump_json(),
        ttl_seconds=60,
    )

    recollected = cache.get_or_collect(
        context,
        _snapshot,
        provider_contract=PROVIDER_CONTRACT,
    )

    assert recollected.status == "MISS"
    assert recollected.snapshot.ticker == "AAPL"


def test_snapshot_with_provider_failure_is_not_shared() -> None:
    calls = 0
    cache = StandardDebateSnapshotCache(
        JsonResponseCache(
            ResilientCacheBackend(LocalCacheBackend()),
            enabled=True,
        )
    )
    context = build_analysis_context("AAPL", as_of="2026-08-28")

    def collect(value: AnalysisContext) -> FactorSnapshot:
        nonlocal calls
        calls += 1
        return FactorSnapshot(
            ticker=value.ticker,
            as_of=value.as_of,
            provider_failures=(
                FactorProviderFailure(
                    provider="optional-provider",
                    provider_version="1",
                    required=False,
                    code="collection_failed",
                    detail="Optional factor provider was omitted from this snapshot.",
                ),
            ),
        )

    first = cache.get_or_collect(
        context,
        collect,
        provider_contract=PROVIDER_CONTRACT,
    )
    second = cache.get_or_collect(
        context,
        collect,
        provider_contract=PROVIDER_CONTRACT,
    )

    assert first.status == second.status == "MISS"
    assert calls == 2
