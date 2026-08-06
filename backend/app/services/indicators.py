from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Iterable


def _round(value: float) -> float:
    return round(value, 4)


def _sma(values: list[float], window: int) -> float:
    sample = values[-window:] if len(values) >= window else values
    return mean(sample) if sample else 0.0


def _ema(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    multiplier = 2 / (window + 1)
    current = values[0]
    for value in values[1:]:
        current = (value - current) * multiplier + current
    return current


def calculate_indicators(ticker: str, prices: Iterable[dict[str, object]]) -> dict[str, object]:
    points = list(prices)
    closes = [float(point["close"]) for point in points]
    volumes = [int(point["volume"]) for point in points]
    changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    gains = [change for change in changes if change > 0]
    losses = [-change for change in changes if change < 0]
    average_gain = mean(gains[-14:]) if gains else 0.0
    average_loss = mean(losses[-14:]) if losses else 0.0
    if average_loss == 0:
        rsi = 100.0 if average_gain else 50.0
    else:
        relative_strength = average_gain / average_loss
        rsi = 100 - (100 / (1 + relative_strength))
    ema_12 = _ema(closes, 12)
    ema_26 = _ema(closes, 26)
    macd = ema_12 - ema_26
    macd_values = [_ema(closes[:index], 12) - _ema(closes[:index], 26) for index in range(2, len(closes) + 1)]
    macd_signal = _ema(macd_values, 9)
    returns = [
        (closes[index] - closes[index - 1]) / closes[index - 1]
        for index in range(1, len(closes))
        if closes[index - 1]
    ]
    volatility = pstdev(returns) * math.sqrt(252) * 100 if len(returns) > 1 else 0.0
    average_volume = mean(volumes[-20:]) if volumes else 0.0
    volume_spike = bool(volumes and average_volume and volumes[-1] > average_volume * 1.35)
    moving_average_20 = _sma(closes, 20)
    moving_average_50 = _sma(closes, 50)
    latest_close = closes[-1] if closes else 0.0
    if latest_close >= moving_average_20 and macd >= macd_signal:
        signal_summary = "Momentum appears constructive, with medium uncertainty."
    elif latest_close < moving_average_20 and macd < macd_signal:
        signal_summary = "Momentum appears pressured, with medium uncertainty."
    else:
        signal_summary = "Signals are mixed and should be interpreted with caution."
    return {
        "ticker": ticker.upper(),
        "as_of": str(points[-1]["date"]) if points else "unknown",
        "rsi": _round(rsi),
        "macd": _round(macd),
        "macd_signal": _round(macd_signal),
        "moving_average_20": _round(moving_average_20),
        "moving_average_50": _round(moving_average_50),
        "volatility": _round(volatility),
        "volume_spike": volume_spike,
        "signal_summary": signal_summary,
    }

