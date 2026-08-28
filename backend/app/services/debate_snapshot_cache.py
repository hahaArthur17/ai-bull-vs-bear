from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.domain.factors import AnalysisContext, FactorSnapshot
from app.services.response_cache import (
    CacheStatus,
    JsonResponseCache,
    standard_debate_snapshot_cache_key,
)


@dataclass(frozen=True)
class FactorSnapshotCacheResult:
    snapshot: FactorSnapshot
    status: CacheStatus


class StandardDebateSnapshotCache:
    """Reuse only public standard-question factor snapshots.

    Session, Message, Job, user identity, and arbitrary question data remain in
    canonical per-user persistence and never enter this shared cache boundary.
    """

    def __init__(
        self,
        cache: JsonResponseCache,
        *,
        ttl_seconds: int = 21_600,
    ) -> None:
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be at least 1")
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    def get_or_collect(
        self,
        context: AnalysisContext,
        collector: Callable[[AnalysisContext], FactorSnapshot],
        *,
        provider_contract: object,
    ) -> FactorSnapshotCacheResult:
        if context.question is not None or context.metadata:
            snapshot = collector(context)
            return FactorSnapshotCacheResult(
                snapshot=snapshot,
                status=self.cache.bypass().status,
            )

        key = standard_debate_snapshot_cache_key(
            context,
            provider_contract=provider_contract,
        )
        cached = self.cache.read(key)
        if isinstance(cached.value, dict):
            snapshot = self._validated_snapshot(cached.value, context)
            if snapshot is not None:
                return FactorSnapshotCacheResult(snapshot=snapshot, status=cached.status)
            read_status: CacheStatus = (
                "DEGRADED" if self.cache.backend.mode == "degraded" else "MISS"
            )
        else:
            read_status = cached.status

        snapshot = collector(context)
        if not snapshot.provider_failures:
            self.cache.write(
                key,
                snapshot.model_dump(mode="json"),
                ttl_seconds=self.ttl_seconds,
            )
        return FactorSnapshotCacheResult(
            snapshot=snapshot,
            status=self.cache.response_status(read_status),
        )

    @staticmethod
    def _validated_snapshot(
        payload: object,
        context: AnalysisContext,
    ) -> FactorSnapshot | None:
        try:
            snapshot = FactorSnapshot.model_validate(payload)
        except (TypeError, ValueError):
            return None
        if snapshot.ticker != context.ticker or snapshot.as_of != context.as_of:
            return None
        if snapshot.provider_failures:
            return None
        for observation in snapshot.observations:
            if observation.ticker != context.ticker:
                return None
            for source in observation.source_refs:
                if (
                    source.source_type == "evidence"
                    and source.source_id not in context.allowed_evidence_ids
                ):
                    return None
        return snapshot
