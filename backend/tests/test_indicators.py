from app.services.demo_store import DemoStore
from app.services.indicators import calculate_indicators


def test_demo_indicators_have_expected_fields() -> None:
    store = DemoStore()
    indicators = calculate_indicators("AAPL", store.get_prices("AAPL"))
    assert 0 <= indicators["rsi"] <= 100
    assert indicators["moving_average_20"] > 0
    assert "signal_summary" in indicators

