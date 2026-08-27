from __future__ import annotations

from app.domain.factors import (
    AnalysisContext,
    FactorDirection,
    FactorFreshness,
    FactorObservation,
    FactorSourceReference,
)
from app.services.indicators import calculate_indicators


class TechnicalFactorProvider:
    """Normalize the existing indicator calculation into factor observations."""

    name = "technical-indicators"
    version = "1"
    required = True

    def collect(self, context: AnalysisContext) -> list[FactorObservation]:
        if not context.prices:
            raise ValueError("Technical factors require a price series")

        prices = [point.model_dump(mode="python") for point in context.prices]
        indicators = calculate_indicators(context.ticker, prices)
        latest_price = context.prices[-1]
        freshness_status = (
            "unknown"
            if latest_price.is_stale is None
            else "stale"
            if latest_price.is_stale
            else "current"
        )
        freshness = FactorFreshness(status=freshness_status)
        source_ref = FactorSourceReference(
            source_type="price",
            source_id=(
                f"{latest_price.source or 'price-series'}:"
                f"{context.ticker}:{context.as_of}"
            ),
            as_of=context.as_of,
        )

        macd_direction = self._relative_direction(
            float(indicators["macd"]),
            float(indicators["macd_signal"]),
        )
        close_direction = self._relative_direction(
            latest_price.close,
            float(indicators["moving_average_20"]),
        )
        common = {
            "ticker": context.ticker,
            "category": "technical",
            "provider": self.name,
            "as_of": context.as_of,
            "confidence": "medium",
            "freshness": freshness,
            "source_refs": (source_ref,),
            "metadata": {"calculation_version": self.version},
            "provider_version": self.version,
        }
        return [
            FactorObservation(
                id=self._id("rsi", context),
                factor_key="technical.rsi",
                label="Relative Strength Index",
                value=float(indicators["rsi"]),
                unit="index points",
                interpretation=(
                    "RSI describes recent gains and losses; it does not predict a future price."
                ),
                direction="neutral",
                **common,  # type: ignore[arg-type]
            ),
            FactorObservation(
                id=self._id("macd", context),
                factor_key="technical.macd",
                label="MACD",
                value={
                    "macd": float(indicators["macd"]),
                    "signal": float(indicators["macd_signal"]),
                },
                unit="price points",
                interpretation=(
                    "MACD relative to its signal line is descriptive momentum context."
                ),
                direction=macd_direction,
                **common,  # type: ignore[arg-type]
            ),
            FactorObservation(
                id=self._id("moving-averages", context),
                factor_key="technical.moving-averages",
                label="Moving averages",
                value={
                    "close": latest_price.close,
                    "ma20": float(indicators["moving_average_20"]),
                    "ma50": float(indicators["moving_average_50"]),
                },
                unit="price",
                interpretation=str(indicators["signal_summary"]),
                direction=close_direction,
                **common,  # type: ignore[arg-type]
            ),
            FactorObservation(
                id=self._id("volatility", context),
                factor_key="technical.volatility",
                label="Annualized volatility",
                value=float(indicators["volatility"]),
                unit="percent",
                interpretation=(
                    "Historical volatility describes variation in observed returns and is not a forecast."
                ),
                direction="neutral",
                **common,  # type: ignore[arg-type]
            ),
            FactorObservation(
                id=self._id("volume-spike", context),
                factor_key="technical.volume-spike",
                label="Volume spike",
                value=bool(indicators["volume_spike"]),
                unit=None,
                interpretation=(
                    "The latest volume is compared with its recent average without assigning causation."
                ),
                direction="mixed" if indicators["volume_spike"] else "neutral",
                **common,  # type: ignore[arg-type]
            ),
        ]

    def _id(self, key: str, context: AnalysisContext) -> str:
        return f"{self.name}:{key}:{context.ticker}:{context.as_of}"

    @staticmethod
    def _relative_direction(value: float, reference: float) -> FactorDirection:
        if value > reference:
            return "supportive"
        if value < reference:
            return "cautionary"
        return "neutral"
