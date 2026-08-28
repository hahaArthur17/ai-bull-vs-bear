from __future__ import annotations

from collections.abc import Iterable

from pydantic import ValidationError

from app.domain.factors import (
    AnalysisContext,
    FactorCategory,
    FactorObservation,
    FactorProvider,
    FactorProviderFailure,
    FactorSnapshot,
)


class FactorRegistryError(RuntimeError):
    """Safe configuration or required-provider failure."""


class FactorRegistry:
    """Collect and validate factor batches without provider-specific branches."""

    def __init__(
        self,
        providers: Iterable[FactorProvider] = (),
        *,
        expected_categories: Iterable[FactorCategory] = (),
    ) -> None:
        self._providers: list[FactorProvider] = []
        self._expected_categories = tuple(dict.fromkeys(expected_categories))
        for provider in providers:
            self.register(provider)

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(provider.name for provider in self._providers)

    @property
    def snapshot_contract(self) -> dict[str, object]:
        """Stable cache identity for the providers that shape one snapshot."""

        return {
            "providers": [
                {
                    "name": provider.name,
                    "version": provider.version,
                    "required": provider.required,
                }
                for provider in self._providers
            ],
            "expected_categories": list(self._expected_categories),
        }

    def register(self, provider: FactorProvider) -> None:
        if not isinstance(provider, FactorProvider):
            raise FactorRegistryError("Factor provider does not implement the required contract")
        if provider.name in self.provider_names:
            raise FactorRegistryError(f"Duplicate factor provider: {provider.name}")
        self._providers.append(provider)

    def collect(self, context: AnalysisContext) -> FactorSnapshot:
        observations: list[FactorObservation] = []
        failures: list[FactorProviderFailure] = []
        seen_ids: set[str] = set()

        for provider in self._providers:
            try:
                raw_batch = provider.collect(context)
            except Exception as exc:
                if provider.required:
                    raise FactorRegistryError(
                        f"Required factor provider failed: {provider.name}"
                    ) from exc
                failures.append(self._failure(provider, "collection_failed"))
                continue

            try:
                batch = [FactorObservation.model_validate(item) for item in raw_batch]
                self._validate_batch(provider, context, batch, seen_ids)
            except (TypeError, ValueError, ValidationError) as exc:
                if provider.required:
                    raise FactorRegistryError(
                        f"Required factor provider returned invalid output: {provider.name}"
                    ) from exc
                failures.append(self._failure(provider, "invalid_output"))
                continue

            observations.extend(batch)
            seen_ids.update(item.id for item in batch)

        present_categories = {item.category for item in observations}
        return FactorSnapshot(
            ticker=context.ticker,
            as_of=context.as_of,
            observations=tuple(observations),
            provider_failures=tuple(failures),
            missing_categories=tuple(
                category
                for category in self._expected_categories
                if category not in present_categories
            ),
        )

    @staticmethod
    def _validate_batch(
        provider: FactorProvider,
        context: AnalysisContext,
        batch: list[FactorObservation],
        seen_ids: set[str],
    ) -> None:
        batch_ids: set[str] = set()
        for item in batch:
            if item.provider != provider.name or item.provider_version != provider.version:
                raise ValueError("Provider identity does not match its factor output")
            if item.ticker != context.ticker:
                raise ValueError("Factor ticker does not match the analysis context")
            if item.id in seen_ids or item.id in batch_ids:
                raise ValueError("Factor observation IDs must be unique in a snapshot")
            for source_ref in item.source_refs:
                if (
                    source_ref.source_type == "evidence"
                    and source_ref.source_id not in context.allowed_evidence_ids
                ):
                    raise ValueError("Factor output referenced evidence outside the allowed set")
            batch_ids.add(item.id)

    @staticmethod
    def _failure(
        provider: FactorProvider,
        code: str,
    ) -> FactorProviderFailure:
        return FactorProviderFailure(
            provider=provider.name,
            provider_version=provider.version,
            required=provider.required,
            code=code,  # type: ignore[arg-type]
            detail=f"Optional factor provider {provider.name} was omitted from this snapshot.",
        )
