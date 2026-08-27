from __future__ import annotations

from typing import Literal

from app.domain.factors import (
    AnalysisContext,
    AnalysisEvidenceItem,
    FactorObservation,
    FactorSourceReference,
)
from app.providers.factor_utils import factor_observation_id


class EvidenceFactorProvider:
    name: str
    version = "1"
    required = False
    source_type: Literal["news", "filing"]
    factor_key: str
    interpretation: str

    def collect(self, context: AnalysisContext) -> list[FactorObservation]:
        return [
            self._observation(context, item)
            for item in context.evidence
            if item.source_type == self.source_type
        ]

    def _observation(
        self,
        context: AnalysisContext,
        item: AnalysisEvidenceItem,
    ) -> FactorObservation:
        return FactorObservation(
            id=factor_observation_id(self.name, item.id),
            ticker=context.ticker,
            factor_key=self.factor_key,
            category="company",
            provider=self.name,
            label=item.title,
            as_of=item.published_at or context.as_of,
            value={"title": item.title, "excerpt": item.excerpt},
            unit=None,
            interpretation=self.interpretation,
            direction="unknown",
            confidence="low",
            freshness=item.freshness,
            source_refs=(
                FactorSourceReference(
                    source_type="evidence",
                    source_id=item.id,
                    url=item.url,
                    as_of=item.published_at,
                ),
            ),
            metadata={"source_type": item.source_type, **item.metadata},
            provider_version=self.version,
        )


class NewsFactorProvider(EvidenceFactorProvider):
    name = "news-evidence"
    source_type = "news"
    factor_key = "company.news-context"
    interpretation = (
        "This dated news item provides company context only; the adapter does not "
        "infer sentiment or claim that the item caused a price move."
    )


class FilingFactorProvider(EvidenceFactorProvider):
    name = "filing-evidence"
    source_type = "filing"
    factor_key = "company.filing-context"
    interpretation = (
        "This filing provides company disclosures and risks for its stated period; "
        "it does not by itself explain a daily price move."
    )

