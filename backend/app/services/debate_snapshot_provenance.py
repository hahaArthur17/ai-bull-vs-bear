from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.services.indicators import COMPLETE_HISTORY_RECORDS, assess_price_history


NEW_YORK = ZoneInfo("America/New_York")


def completed_close_cutoff(captured_at: datetime) -> date:
    """Return a conservative US daily-candle cutoff for a capture instant.

    The cutoff intentionally does not attempt to infer exchange holidays. On a
    holiday the newest real provider row remains an earlier date, which is safe;
    live admission separately rejects stale history.
    """

    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("Snapshot capture time must include a timezone")
    market_now = captured_at.astimezone(NEW_YORK)
    candidate = market_now.date()
    if market_now.weekday() >= 5 or market_now.time() < time(16, 15):
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def require_live_debate_history(
    prices: list[dict[str, object]],
    *,
    captured_at: datetime,
) -> None:
    assessment = assess_price_history(
        prices,
        completed_through=completed_close_cutoff(captured_at),
    )
    if not assessment["is_valid"]:
        raise ValueError(str(assessment["explanation"]))
    if assessment["provenance"] != "live_fresh":
        raise ValueError("Live Debate requires fresh verified daily history")
    if int(assessment["completed_close_count"]) < COMPLETE_HISTORY_RECORDS:
        raise ValueError(
            f"Live Debate requires at least {COMPLETE_HISTORY_RECORDS} completed closes"
        )


def quote_session(as_of: datetime) -> str:
    market_time = as_of.astimezone(NEW_YORK)
    if market_time.weekday() >= 5:
        return "closed"
    value = market_time.time()
    if value < time(9, 30):
        return "pre_market"
    if value < time(16):
        return "regular"
    if value < time(20):
        return "after_hours"
    return "closed"
