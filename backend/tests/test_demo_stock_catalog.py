from app.services.demo_store import DemoStore


def test_demo_catalog_keeps_default_list_bounded_to_debate_ready() -> None:
    stocks = DemoStore().list_stocks()

    assert {stock["ticker"] for stock in stocks} == {"AAPL", "GOOG", "NVDA", "TSLA"}
    assert all(stock["coverage_status"] == "debate_ready" for stock in stocks)


def test_demo_catalog_search_identifies_catalog_only_ticker() -> None:
    store = DemoStore()

    exact = store.list_stocks("MSFT")
    by_company = store.list_stocks("microsoft")

    assert exact[0]["ticker"] == "MSFT"
    assert exact[0]["coverage_status"] == "catalog_only"
    assert exact[0]["sector"] is None
    assert by_company[0]["ticker"] == "MSFT"


def test_demo_catalog_search_ranks_and_limits_results() -> None:
    results = DemoStore().list_stocks("AA", limit=3)

    assert len(results) == 3
    assert results[0]["ticker"] == "AA"
    assert all(str(stock["ticker"]).startswith("AA") for stock in results)


def test_demo_watchlist_accepts_catalog_only_ticker() -> None:
    store = DemoStore()

    assert store.get_stock("MSFT") is not None
    assert store.add_watchlist("catalog-user", "msft") == ["MSFT"]
