from datetime import datetime, timezone

import pytest

from app.services.debate_snapshot_provenance import (
    completed_close_cutoff,
    require_live_debate_history,
)


def _prices(count: int = 50) -> list[dict[str, object]]:
    # Business-day precision is irrelevant to validation; these are provider
    # rows ending safely before the asserted cutoff.
    from datetime import date, timedelta

    start = date(2026, 6, 1)
    return [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "open": 100 + index,
            "high": 102 + index,
            "low": 99 + index,
            "close": 101 + index,
            "volume": 1_000 + index,
            "source": "daily_market_cache",
            "is_stale": False,
        }
        for index in range(count)
    ]


def test_completed_close_cutoff_never_treats_regular_session_today_as_complete() -> None:
    assert completed_close_cutoff(datetime(2026, 8, 19, 18, tzinfo=timezone.utc)).isoformat() == "2026-08-18"
    assert completed_close_cutoff(datetime(2026, 8, 19, 21, tzinfo=timezone.utc)).isoformat() == "2026-08-19"
    assert completed_close_cutoff(datetime(2026, 8, 23, 18, tzinfo=timezone.utc)).isoformat() == "2026-08-21"


def test_live_history_fails_closed_for_insufficient_stale_and_intraday_rows() -> None:
    captured_at = datetime(2026, 8, 19, 18, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="at least 50"):
        require_live_debate_history(_prices(49), captured_at=captured_at)

    stale = _prices()
    stale[-1]["is_stale"] = True
    with pytest.raises(ValueError, match="fresh verified"):
        require_live_debate_history(stale, captured_at=captured_at)

    intraday = _prices()
    intraday[-1]["date"] = "2026-08-19"
    with pytest.raises(ValueError, match="completed-candle cutoff"):
        require_live_debate_history(intraday, captured_at=captured_at)
