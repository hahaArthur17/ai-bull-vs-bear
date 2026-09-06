from datetime import date, timedelta

from app.services.demo_store import DemoStore
from app.services.indicators import assess_price_history, calculate_indicators


def price_points(count: int, *, source: str = "daily_market_cache") -> list[dict[str, object]]:
    return [
        {
            "date": (date(2026, 1, 1) + timedelta(days=index)).isoformat(),
            "open": 99 + index * 0.7 + ((index % 5) - 2) * 0.9,
            "high": 102 + index * 0.7 + ((index % 5) - 2) * 0.9,
            "low": 98 + index * 0.7 + ((index % 5) - 2) * 0.9,
            "close": 100 + index * 0.7 + ((index % 5) - 2) * 0.9,
            "volume": 1_000 + index * 10,
            "source": source,
            "is_stale": False,
        }
        for index in range(count)
    ]


def test_demo_indicators_have_expected_fields() -> None:
    store = DemoStore()
    indicators = calculate_indicators("AAPL", store.get_prices("AAPL"))
    assert 0 <= indicators["rsi"] <= 100
    assert indicators["moving_average_20"] == 0
    assert indicators["history"]["provenance"] == "unavailable"
    assert not any(indicators["availability"].values())
    assert "signal_summary" in indicators


def test_indicator_golden_vector_matches_canonical_contract() -> None:
    indicators = calculate_indicators("aapl", price_points(55))

    assert indicators["ticker"] == "AAPL"
    assert indicators["rsi"] == 72.9231
    assert indicators["macd"] == 4.9502
    assert indicators["macd_signal"] == 4.7633
    assert indicators["moving_average_20"] == 131.15
    assert indicators["moving_average_50"] == 120.65
    assert indicators["volatility"] == 22.012
    assert indicators["history"]["complete_view"] is True
    assert all(indicators["availability"].values())


def test_history_threshold_degrades_each_series_independently() -> None:
    nineteen = calculate_indicators("AAPL", price_points(19))
    forty_nine = calculate_indicators("AAPL", price_points(49))
    fifty = calculate_indicators("AAPL", price_points(50))

    assert nineteen["availability"]["price_line"] is True
    assert nineteen["availability"]["rsi"] is True
    assert nineteen["availability"]["moving_average_20"] is False
    assert nineteen["history"]["complete_view"] is False
    assert forty_nine["availability"]["moving_average_20"] is True
    assert forty_nine["availability"]["moving_average_50"] is False
    assert forty_nine["history"]["complete_view"] is False
    assert fifty["availability"]["moving_average_50"] is True
    assert fifty["history"]["complete_view"] is True


def test_review_fixture_history_never_describes_simulated_closes_as_verified() -> None:
    nineteen = calculate_indicators("AAPL", price_points(19, source="review_fixture"))
    fifty = calculate_indicators("AAPL", price_points(50, source="review_fixture"))

    assert nineteen["history"]["provenance"] == "review_fixture"
    assert nineteen["history"]["explanation"] == (
        "19 simulated review closes are available; 50 are required for the complete technical view."
    )
    assert fifty["history"]["explanation"] == (
        "Simulated review history is sufficient for the complete technical view."
    )


def test_invalid_or_unverified_history_never_claims_complete() -> None:
    duplicate = price_points(50)
    duplicate[20]["date"] = duplicate[19]["date"]
    out_of_order = price_points(50)
    out_of_order[20], out_of_order[21] = out_of_order[21], out_of_order[20]

    for points in (duplicate, out_of_order, price_points(55, source="demo_fallback")):
        indicators = calculate_indicators("AAPL", points)
        assert indicators["history"]["complete_view"] is False
        assert not any(indicators["availability"].values())
        assert indicators["moving_average_20"] == 0
        assert "unavailable" in indicators["signal_summary"].lower()

    future = assess_price_history(price_points(2), completed_through=date(2026, 1, 1))
    assert future["has_only_completed_closes"] is False
    assert future["is_valid"] is False


def test_invalid_or_missing_ohlcv_is_safely_unavailable() -> None:
    invalid_histories = []
    negative_volume = price_points(50)
    negative_volume[-1]["volume"] = -1
    invalid_histories.append(negative_volume)
    inconsistent_range = price_points(50)
    inconsistent_range[-1]["high"] = float(inconsistent_range[-1]["close"]) - 1
    invalid_histories.append(inconsistent_range)
    missing_open = price_points(50)
    missing_open[-1].pop("open")
    invalid_histories.append(missing_open)
    missing_date = price_points(50)
    missing_date[-1].pop("date")
    invalid_histories.append(missing_date)

    for points in invalid_histories[:3]:
        assert calculate_indicators("AAPL", points)["history"]["has_valid_ohlcv"] is False

    for points in invalid_histories:
        indicators = calculate_indicators("AAPL", points)
        assert indicators["history"]["is_valid"] is False
        assert not any(indicators["availability"].values())
        assert indicators["rsi"] == 0
        assert "unavailable" in indicators["signal_summary"].lower()


def test_stale_verified_history_stays_usable_with_explicit_provenance() -> None:
    points = price_points(50)
    for point in points:
        point["is_stale"] = True

    indicators = calculate_indicators("AAPL", points)

    assert indicators["history"]["provenance"] == "live_stale"
    assert indicators["history"]["complete_view"] is True
    assert indicators["availability"]["price_line"] is True
