#!/usr/bin/env python3
"""Fetch one bounded macro context history and write it to Supabase."""

from __future__ import annotations

import json

from app.config import get_settings
from app.services.macro_data import EiaClient, FredClient, MacroDataWriter, ingest_macro_context


def main() -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SECRET_KEY are required")
    if not settings.fred_api_key or not settings.eia_api_key:
        raise SystemExit("FRED_API_KEY and EIA_API_KEY are required")
    result = ingest_macro_context(
        MacroDataWriter(settings.supabase_url, settings.supabase_secret_key),
        FredClient(settings.fred_api_key),
        EiaClient(settings.eia_api_key),
        limit_per_series=settings.macro_history_points,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
