#!/usr/bin/env python3
from __future__ import annotations

import json

from app.config import get_settings
from app.services.market_data import (
    AlphaVantageClient,
    FinnhubClient,
    SupabasePriceWriter,
    ingest_live_prices,
)


def main() -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    if settings.alpha_vantage_api_key:
        provider = AlphaVantageClient(settings.alpha_vantage_api_key, max_attempts=1)
    elif settings.finnhub_api_key:
        provider = FinnhubClient(settings.finnhub_api_key)
    else:
        raise SystemExit("ALPHA_VANTAGE_API_KEY or FINNHUB_API_KEY is required")
    writer = SupabasePriceWriter(settings.supabase_url, settings.supabase_secret_key)
    print(
        json.dumps(
            ingest_live_prices(
                provider,
                writer,
                tickers=settings.price_ticker_list,
                max_provider_calls=settings.price_max_calls_per_run,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
