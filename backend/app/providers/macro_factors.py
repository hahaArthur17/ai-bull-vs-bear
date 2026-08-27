from __future__ import annotations

from app.domain.factors import (
    AnalysisContext,
    FactorObservation,
    FactorSourceReference,
)
from app.providers.factor_utils import factor_key_segment, factor_observation_id


class MacroFactorProvider:
    """Normalize cached, dated macro observations as non-causal background."""

    name = "macro-context"
    version = "1"
    required = False

    def collect(self, context: AnalysisContext) -> list[FactorObservation]:
        return [
            FactorObservation(
                id=factor_observation_id(
                    self.name,
                    observation.code,
                    observation.observation_date,
                ),
                ticker=context.ticker,
                factor_key=f"macro.{factor_key_segment(observation.code)}",
                category="macro",
                provider=self.name,
                label=observation.name,
                as_of=observation.observation_date,
                value=observation.value,
                unit=observation.unit,
                interpretation=(
                    "This dated market observation is broad background only; it does not "
                    "establish why the stock moved or predict a future outcome."
                ),
                direction="neutral",
                confidence="medium",
                source_refs=(
                    FactorSourceReference(
                        source_type="macro",
                        source_id=observation.code,
                        as_of=observation.observation_date,
                    ),
                ),
                metadata={
                    "source": observation.source,
                    "retrieved_at": observation.retrieved_at,
                    **observation.metadata,
                },
                provider_version=self.version,
            )
            for observation in context.macro_context
        ]

