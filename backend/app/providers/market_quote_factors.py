from __future__ import annotations

from app.domain.factors import AnalysisContext, FactorObservation, FactorSourceReference


class MarketQuoteFactorProvider:
    """Expose a frozen quote without feeding it into daily indicator math."""

    name = "market-quote"
    version = "1"
    required = False

    def collect(self, context: AnalysisContext) -> list[FactorObservation]:
        quote = context.market_quote
        if quote is None:
            return []
        return [
            FactorObservation(
                id=f"market-quote:{context.ticker}:{quote.as_of.isoformat()}",
                ticker=context.ticker,
                factor_key="market.latest-provider-quote",
                category="other",
                provider=self.name,
                label="Latest provider quote",
                as_of=quote.as_of.isoformat(),
                value={
                    "price": quote.close,
                    "open": quote.open,
                    "high": quote.high,
                    "low": quote.low,
                    "previous_close": quote.previous_close,
                },
                unit="USD",
                interpretation=(
                    "This is a provider quote observation and is not part of the completed-close series used for technical indicators."
                ),
                direction="neutral",
                confidence="medium",
                freshness=quote.freshness,
                source_refs=(
                    FactorSourceReference(
                        source_type="quote",
                        source_id=f"{quote.source}:{context.ticker}:{quote.as_of.isoformat()}",
                        as_of=quote.as_of.isoformat(),
                    ),
                ),
                metadata={
                    "retrieved_at": quote.retrieved_at.isoformat(),
                    "captured_at": context.captured_at.isoformat() if context.captured_at else None,
                    "market_session": quote.market_session,
                    "latest_completed_close_date": context.latest_completed_close_date,
                },
                provider_version=self.version,
            )
        ]
