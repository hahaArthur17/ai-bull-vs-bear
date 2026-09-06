from __future__ import annotations

from datetime import date, datetime, timezone
import math
from statistics import mean, pstdev
from typing import Iterable


COMPLETE_HISTORY_RECORDS = 50
RSI_PERIOD = 14
VOLATILITY_PERIOD = 20
TRADING_DAYS_PER_YEAR = 252


def _round(value: float) -> float:
    return round(value, 4)


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _ema_series(values: list[float], window: int) -> list[float]:
    if not values:
        return []
    multiplier = 2 / (window + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * multiplier + result[-1] * (1 - multiplier))
    return result


def _latest_rsi(values: list[float], period: int = RSI_PERIOD) -> float | None:
    if len(values) <= period:
        return None
    changes = [values[index] - values[index - 1] for index in range(1, len(values))]
    average_gain = mean(max(change, 0.0) for change in changes[:period])
    average_loss = mean(max(-change, 0.0) for change in changes[:period])
    for change in changes[period:]:
        average_gain = (average_gain * (period - 1) + max(change, 0.0)) / period
        average_loss = (average_loss * (period - 1) + max(-change, 0.0)) / period
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def _latest_volatility(values: list[float], period: int = VOLATILITY_PERIOD) -> float | None:
    if len(values) <= period:
        return None
    window = values[-(period + 1):]
    returns = [
        math.log(window[index] / window[index - 1])
        for index in range(1, len(window))
    ]
    return pstdev(returns) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100


def assess_price_history(
    prices: Iterable[dict[str, object]],
    *,
    completed_through: date | None = None,
) -> dict[str, object]:
    """Describe whether daily closes are safe to use for technical displays.

    Daily providers in this project expose date-only completed candles. A date
    later than the UTC calendar date is therefore rejected. The function never
    sorts or removes rows: duplicate or out-of-order input remains visibly
    invalid instead of being silently repaired.
    """

    points = list(prices)
    cutoff = completed_through or datetime.now(timezone.utc).date()
    parsed_dates: list[date] = []
    valid_closes = True
    valid_ohlcv = True
    valid_dates = True
    for point in points:
        try:
            parsed_dates.append(date.fromisoformat(str(point["date"])))
        except (KeyError, TypeError, ValueError):
            valid_dates = False
        try:
            close = float(point["close"])
            if not math.isfinite(close) or close <= 0:
                valid_closes = False
        except (KeyError, TypeError, ValueError, OverflowError):
            valid_closes = False
        try:
            open_price = float(point["open"])
            high = float(point["high"])
            low = float(point["low"])
            close = float(point["close"])
            volume = int(point["volume"])
            if not all(
                math.isfinite(value) and value > 0
                for value in (open_price, high, low, close)
            ):
                valid_ohlcv = False
            if high < max(open_price, close) or low > min(open_price, close) or low > high:
                valid_ohlcv = False
            if volume < 0:
                valid_ohlcv = False
        except (KeyError, TypeError, ValueError, OverflowError):
            valid_ohlcv = False

    is_ordered = valid_dates and all(
        parsed_dates[index] < parsed_dates[index + 1]
        for index in range(len(parsed_dates) - 1)
    )
    has_unique_dates = valid_dates and len(set(parsed_dates)) == len(parsed_dates)
    completed_close_count = sum(item <= cutoff for item in parsed_dates) if valid_dates else 0
    has_only_completed_closes = valid_dates and completed_close_count == len(points)
    is_valid = bool(
        points
        and valid_dates
        and valid_closes
        and valid_ohlcv
        and is_ordered
        and has_unique_dates
        and has_only_completed_closes
    )

    sources = {str(point.get("source", "")) for point in points}
    if sources == {"daily_market_cache"}:
        provenance = "live_stale" if any(bool(point.get("is_stale", True)) for point in points) else "live_fresh"
    elif sources == {"review_fixture"}:
        provenance = "review_fixture"
    else:
        provenance = "unavailable"
    has_verified_provenance = provenance in {"live_fresh", "live_stale", "review_fixture"}
    usable_count = len(points) if is_valid and has_verified_provenance else 0

    availability = {
        "price_line": usable_count >= 2,
        "price_change": usable_count >= 2,
        "moving_average_20": usable_count >= 20,
        "moving_average_50": usable_count >= 50,
        "rsi": usable_count >= RSI_PERIOD + 1,
        "macd": usable_count >= 26,
        "macd_signal": usable_count >= 34,
        "volume": usable_count >= 1,
        "volatility": usable_count >= VOLATILITY_PERIOD + 1,
    }
    complete_view = bool(is_valid and has_verified_provenance and len(points) >= COMPLETE_HISTORY_RECORDS)

    if not points:
        explanation = "No daily close history is available."
    elif not valid_dates or not valid_closes or not valid_ohlcv:
        explanation = "Daily history contains an invalid date or OHLCV value."
    elif not has_unique_dates:
        explanation = "Daily history contains duplicate close dates."
    elif not is_ordered:
        explanation = "Daily history is not strictly chronological."
    elif not has_only_completed_closes:
        explanation = "Daily history contains a close after the completed-candle cutoff."
    elif not has_verified_provenance:
        explanation = "Daily history provenance is not verified for market presentation."
    elif len(points) < COMPLETE_HISTORY_RECORDS:
        history_label = "simulated review closes" if provenance == "review_fixture" else "verified closes"
        explanation = f"{len(points)} {history_label} are available; {COMPLETE_HISTORY_RECORDS} are required for the complete technical view."
    elif provenance == "review_fixture":
        explanation = "Simulated review history is sufficient for the complete technical view."
    else:
        explanation = "Verified daily history is sufficient for the complete technical view."

    return {
        "provenance": provenance,
        "record_count": len(points),
        "completed_close_count": completed_close_count,
        "required_for_complete": COMPLETE_HISTORY_RECORDS,
        "is_ordered": is_ordered,
        "has_unique_dates": has_unique_dates,
        "has_valid_closes": valid_closes,
        "has_valid_ohlcv": valid_ohlcv,
        "has_only_completed_closes": has_only_completed_closes,
        "is_valid": is_valid,
        "complete_view": complete_view,
        "explanation": explanation,
        "availability": availability,
    }


def validate_completed_daily_prices(
    prices: Iterable[dict[str, object]],
    *,
    completed_through: date | None = None,
) -> list[dict[str, object]]:
    points = list(prices)
    assessment = assess_price_history(
        [{**point, "source": "daily_market_cache", "is_stale": False} for point in points],
        completed_through=completed_through,
    )
    if not assessment["is_valid"]:
        raise ValueError(str(assessment["explanation"]))
    for point in points:
        try:
            open_price = float(point["open"])
            high = float(point["high"])
            low = float(point["low"])
            close = float(point["close"])
            volume = int(point["volume"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Daily history contains an invalid OHLCV value.") from exc
        if not all(math.isfinite(value) and value > 0 for value in (open_price, high, low, close)):
            raise ValueError("Daily history contains a non-positive or non-finite OHLC value.")
        if high < max(open_price, close) or low > min(open_price, close) or low > high:
            raise ValueError("Daily history contains an inconsistent OHLC range.")
        if volume < 0:
            raise ValueError("Daily history contains a negative volume.")
    return points


def calculate_indicators(ticker: str, prices: Iterable[dict[str, object]]) -> dict[str, object]:
    points = list(prices)
    history = assess_price_history(points)
    is_available = bool(history["is_valid"] and history["provenance"] != "unavailable")
    closes = [float(point["close"]) for point in points] if is_available else []
    volumes = [int(point["volume"]) for point in points] if is_available else []

    moving_average_20 = _sma(closes, 20)
    moving_average_50 = _sma(closes, 50)
    rsi = _latest_rsi(closes)
    ema_12 = _ema_series(closes, 12)
    ema_26 = _ema_series(closes, 26)
    macd_series = [short - long for short, long in zip(ema_12, ema_26, strict=True)]
    signal_series = _ema_series(macd_series, 9)
    macd = macd_series[-1] if len(closes) >= 26 else None
    macd_signal = signal_series[-1] if len(closes) >= 34 else None
    volatility = _latest_volatility(closes)
    average_volume = mean(volumes[-20:]) if len(volumes) >= 20 else None
    volume_spike = bool(average_volume and volumes[-1] > average_volume * 1.35)
    latest_close = closes[-1] if closes else None

    if latest_close is None or moving_average_20 is None or macd is None or macd_signal is None:
        signal_summary = "Technical signals are unavailable until sufficient valid history is present."
    elif latest_close >= moving_average_20 and macd >= macd_signal:
        signal_summary = "Momentum appears constructive, with medium uncertainty."
    elif latest_close < moving_average_20 and macd < macd_signal:
        signal_summary = "Momentum appears pressured, with medium uncertainty."
    else:
        signal_summary = "Signals are mixed and should be interpreted with caution."

    availability = history.pop("availability")
    # Scalar fields stay numeric for compatibility. Presentation must consult
    # availability before showing them.
    return {
        "ticker": ticker.upper(),
        "as_of": str(points[-1].get("date", "unknown")) if points else "unknown",
        "rsi": _round(rsi or 0.0),
        "macd": _round(macd or 0.0),
        "macd_signal": _round(macd_signal or 0.0),
        "moving_average_20": _round(moving_average_20 or 0.0),
        "moving_average_50": _round(moving_average_50 or 0.0),
        "volatility": _round(volatility or 0.0),
        "volume_spike": volume_spike,
        "signal_summary": signal_summary,
        "availability": availability,
        "history": history,
    }
