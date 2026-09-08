from datetime import datetime, timezone

import httpx
import pytest

from app.services.debate_financial_admission import LiveFinancialFactsUnavailable, select_live_financial_facts
from app.services.supabase_store import SupabaseStore

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


def fact(**changes):
    return {**dict(id="fact1", ticker="AAPL", taxonomy="us-gaap", concept="Revenue", label="Revenue",
        unit="USD", value=123, period_start="2026-04-01", period_end="2026-06-30", filed_at="2026-08-01",
        form="10-Q", accession_number="0000320193-26-000001",
        source_url="https://www.sec.gov/Archives/edgar/data/320193/000032019326000001/",
        metadata={"storage": "supabase"}), **changes}


def select(rows):
    return select_live_financial_facts("AAPL", rows, captured_at=NOW, cik=320193)


def test_periods_and_units_remain_distinct_and_latest_filing_wins():
    selected = select([fact(), fact(id="revision", filed_at="2026-08-02", value=125),
                       fact(id="other-period", period_start="2026-01-01")])
    assert {f.id for f in selected} == {"revision", "other-period"}


@pytest.mark.parametrize("changes", [
    {"source_url": "https://sec.gov.evil.com/Archives/"}, {"ticker": "MSFT"},
    {"period_start": "2026-07-01"}, {"filed_at": "2099-01-01"},
    {"period_end": "2024-01-01"}, {"metadata": {}}, {"value": float("nan")},
    {"accession_number": "bad"}, {"form": "8-K"},
])
def test_bad_provenance_and_periods_fail_closed(changes):
    with pytest.raises(LiveFinancialFactsUnavailable):
        select([fact(**changes)])


def test_conflicting_values_cannot_silently_override():
    with pytest.raises(LiveFinancialFactsUnavailable, match="Conflicting"):
        select([fact(), fact(id="other", value=999)])


def test_public_reader_is_ticker_scoped_and_bounded():
    def handler(request):
        assert request.headers["apikey"] == "test-public"
        if request.url.path.endswith("/stocks"):
            assert request.url.params["ticker"] == "eq.AAPL"
            return httpx.Response(200, json=[{"id": 7}])
        assert request.url.path.endswith("/financial_facts")
        assert request.url.params["stock_id"] == "eq.7"
        assert request.url.params["limit"] == "200"
        return httpx.Response(200, json=[{**fact(), "id": 12}])
    store = SupabaseStore("https://example.test", "test-public", client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = store.get_financial_facts("aapl")
    assert result[0]["id"] == "financial-fact:12"
    assert result[0]["ticker"] == "AAPL"
