from __future__ import annotations

from app.domain.factors import (
    AnalysisContext,
    FactorFreshness,
    FactorObservation,
    FactorSourceReference,
)
from app.providers.factor_utils import factor_key_segment, factor_observation_id


class FinancialFactsProvider:
    """Expose structured filing facts without inventing comparison semantics."""

    name = "financial-facts"
    version = "1"
    required = False

    def collect(self, context: AnalysisContext) -> list[FactorObservation]:
        return [
            FactorObservation(
                id=factor_observation_id(self.name, fact.id),
                ticker=context.ticker,
                factor_key=(
                    "fundamental."
                    f"{factor_key_segment(fact.taxonomy, max_length=24)}."
                    f"{factor_key_segment(fact.concept, max_length=64)}"
                ),
                category="fundamental",
                provider=self.name,
                label=fact.label,
                as_of=fact.period_end,
                value=fact.value,
                unit=fact.unit,
                interpretation=(
                    f"This is a reported {fact.label} value for {fact.period_start} "
                    f"through {fact.period_end}; comparisons require matching units, "
                    "periods, and filing context."
                ),
                direction="unknown",
                confidence="medium",
                freshness=FactorFreshness(status="unknown"),
                source_refs=(
                    FactorSourceReference(
                        source_type="financial_fact",
                        source_id=fact.id,
                        url=fact.source_url,
                        as_of=fact.filed_at,
                    ),
                ),
                metadata={
                    "taxonomy": fact.taxonomy,
                    "concept": fact.concept,
                    "period_start": fact.period_start,
                    "period_end": fact.period_end,
                    "filed_at": fact.filed_at,
                    "form": fact.form,
                    "accession_number": fact.accession_number,
                    "fiscal_year": fact.fiscal_year,
                    "fiscal_period": fact.fiscal_period,
                    **fact.metadata,
                },
                provider_version=self.version,
            )
            for fact in context.financial_facts
        ]

