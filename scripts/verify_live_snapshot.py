#!/usr/bin/env python3
"""Offline WP8L consistency audit of a saved Session and research bundle.

No settings, credentials, provider calls, or database writes are used. A pass
proves consistency of the supplied capture, not current upstream availability.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from app.domain.factors import AnalysisContext, FactorSnapshot
from app.schemas import StockBundle
from app.services.indicators import assess_price_history, calculate_indicators
from app.services.debate_snapshot_provenance import completed_close_cutoff, quote_session


def _instant(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def _dated_before(value: object, capture: datetime | None) -> bool:
    if capture is None:
        return False
    try:
        return date.fromisoformat(str(value)) <= capture.date()
    except ValueError:
        parsed = _instant(value)
        return parsed is not None and parsed <= capture


def audit_capture(payload: object) -> dict[str, object]:
    try:
        if not isinstance(payload, dict):
            raise ValueError("capture shape")
        session = payload["session"]
        context = AnalysisContext.model_validate(session["analysis_context"])
        snapshot = FactorSnapshot.model_validate(session["factor_snapshot"])
        bundle = StockBundle.model_validate(payload["bundle"])
    except (KeyError, TypeError, ValueError):
        return {"passed": False, "checks": {"schema": False}}

    prices = [point.model_dump(mode="json") for point in context.prices]
    capture = context.captured_at
    history = assess_price_history(prices, completed_through=(
        completed_close_cutoff(capture) if capture else date.min))
    expected_indicators = calculate_indicators(context.ticker, prices) if prices else {}
    quote = context.market_quote
    quote_factors = [item for item in snapshot.observations
                     if item.factor_key == "market.latest-provider-quote"]
    checks = {
        "aapl_standard": context.ticker == snapshot.ticker == bundle.stock.ticker == "AAPL"
        and bundle.data_mode == "standard",
        "capture_time": context.captured_at is not None,
        "snapshot_date": context.as_of == snapshot.as_of == context.latest_completed_close_date,
        "daily_history": bool(history.get("is_valid")) and len(prices) >= 50,
        "daily_provenance": bool(prices) and all(
            point["source"] == "daily_market_cache" and point["is_stale"] is False
            for point in prices),
        "completed_close": bool(prices) and context.latest_completed_close_date == prices[-1]["date"],
        "page_history": prices == [
            {key: point.model_dump(mode="json").get(key) for key in prices[0]}
            for point in bundle.prices] if prices else False,
        "page_indicators": bool(prices) and all(
            bundle.indicators.model_dump().get(key) == expected_indicators.get(key)
            for key in ("ticker", "as_of", "rsi", "macd", "macd_signal",
                        "moving_average_20", "moving_average_50", "volatility", "volume_spike")),
        "quote_current": quote is not None and quote.freshness.status == "current"
        and capture is not None and quote.as_of <= quote.retrieved_at <= capture
        and (capture - quote.as_of).total_seconds() <= (
            900 if quote_session(capture) == "regular" else 259200),
        "quote_factor": len(quote_factors) == 1 and quote is not None
        and isinstance(quote_factors[0].value, dict)
        and quote_factors[0].value.get("price") == quote.close
        and quote_factors[0].as_of == quote.as_of.isoformat(),
        "page_quote": quote is not None and bundle.quote is not None
        and quote.close == bundle.quote.close
        and quote.as_of == _instant(bundle.quote.as_of)
        and quote.ticker == bundle.quote.ticker
        and quote.source == bundle.quote.source
        and quote.retrieved_at == _instant(bundle.quote.retrieved_at),
        "evidence_provenance": bool(context.evidence) and all(
            _dated_before(item.published_at, capture) and item.url
            and item.url.startswith(("https://", "http://")) and item.freshness.status == "current"
            for item in context.evidence),
        "page_evidence": {(item.id, item.source_type, item.published_at) for item in context.evidence}
        == {(item.id, item.source_type, item.published_at) for item in bundle.evidence},
        "page_macro": all(any(
            series.series.code == item.code and any(
                row.observation_date == item.observation_date and row.value == item.value
                for row in series.observations)
            for series in bundle.macro_context) for item in context.macro_context),
        "factor_evidence_allowlist": all(
            ref.source_id in context.allowed_evidence_ids
            for item in snapshot.observations for ref in item.source_refs
            if ref.source_type == "evidence"),
        "factor_providers": not snapshot.provider_failures,
        "macro_provenance": len({item.code for item in context.macro_context}) >= 7 and all(
            _dated_before(item.observation_date, capture)
            and _dated_before(item.retrieved_at, capture) and item.source
            for item in context.macro_context),
    }
    checks = {key: bool(value) for key, value in checks.items()}
    return {
        "passed": all(checks.values()),
        "scope": "offline_capture_consistency_only",
        "checks": checks,
        "daily_rows": len(prices),
        "evidence_rows": len(context.evidence),
        "macro_rows": len(context.macro_context),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="JSON containing session and bundle from the same capture")
    args = parser.parse_args()
    try:
        # Bounded input; never echo paths, raw values, schema errors, or excerpts.
        with args.input.open("rb") as handle:
            raw = handle.read(4_000_001)
        result = audit_capture(json.loads(raw)) if len(raw) <= 4_000_000 else {"passed": False, "error": "input_too_large"}
    except (OSError, ValueError):
        result = {"passed": False, "error": "invalid_capture"}
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
