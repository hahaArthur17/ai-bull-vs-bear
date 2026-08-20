#!/usr/bin/env python3
"""Refresh AAPL's labelled weekly history once per week."""

from __future__ import annotations

import json

from app.config import get_settings
from app.services.market_data import (
    AlphaVantageClient,
    SupabasePriceWriter,
    ingest_weekly_price_history,
)


def main() -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    if not settings.alpha_vantage_api_key:
        raise SystemExit("ALPHA_VANTAGE_API_KEY is required")
    print(
        json.dumps(
            ingest_weekly_price_history(
                AlphaVantageClient(settings.alpha_vantage_api_key, max_attempts=1),
                SupabasePriceWriter(settings.supabase_url, settings.supabase_secret_key),
                limit=settings.weekly_price_history_points,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
