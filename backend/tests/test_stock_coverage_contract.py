import pytest
from pydantic import ValidationError

from app.schemas import Stock, StockCoverage
from app.services.demo_store import DemoStore


def test_demo_stocks_are_explicitly_debate_ready() -> None:
    stocks = [Stock.model_validate(stock) for stock in DemoStore().list_stocks()]

    assert {stock.ticker for stock in stocks} == {"AAPL", "GOOG", "NVDA", "TSLA"}
    assert all(stock.coverage_status == "debate_ready" for stock in stocks)
    assert all(stock.sec_cik for stock in stocks)


def test_catalog_only_stock_allows_unknown_classification() -> None:
    stock = Stock.model_validate(
        {
            "ticker": "MSFT",
            "company_name": "MICROSOFT CORP",
            "exchange": "NASDAQ",
        }
    )

    assert stock.sector is None
    assert stock.country is None
    assert stock.coverage_status == "catalog_only"
    assert stock.aliases == []


def test_stock_and_coverage_contract_reject_unknown_coverage_state() -> None:
    with pytest.raises(ValidationError):
        Stock.model_validate(
            {
                "ticker": "MSFT",
                "company_name": "MICROSOFT CORP",
                "exchange": "NASDAQ",
                "coverage_status": "unknown",
            }
        )
    with pytest.raises(ValidationError):
        StockCoverage.model_validate(
            {
                "ticker": "MSFT",
                "coverage_status": "unknown",
                "has_price_data": False,
                "has_evidence": False,
                "can_debate": False,
            }
        )
