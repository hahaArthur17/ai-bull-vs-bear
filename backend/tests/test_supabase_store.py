from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx

from app.services.analysis import AnalysisService
from app.services.demo_store import DemoStore
from app.services.supabase_store import SupabaseStore


class FakePostgrest:
    def __init__(self) -> None:
        self.watchlist: set[int] = set()
        self.analysis_ids: list[str] = []
        self.responses: dict[str, dict[str, object]] = {}
        self.price_rows: list[dict[str, object]] = []
        self.price_status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "anon-key"
        assert request.headers["authorization"] in {"Bearer user-token", "Bearer anon-key"}
        table = request.url.path.rsplit("/", 1)[-1]
        query = parse_qs(request.url.query.decode())
        body = __import__("json").loads(request.content or b"null")
        if table == "stocks":
            return httpx.Response(200, json=[{"id": 1}])
        if table == "stock_prices":
            return httpx.Response(self.price_status, json=self.price_rows)
        if table == "macro_series":
            return httpx.Response(
                200,
                json=[
                    {
                        "code": "vix",
                        "name": "CBOE Volatility Index",
                        "source": "fred",
                        "unit": "index points",
                        "frequency": "daily",
                        "metadata": {"provider_series_id": "VIXCLS"},
                    }
                ],
            )
        if table == "macro_observations":
            return httpx.Response(
                200,
                json=[
                    {
                        "series_code": "vix",
                        "observation_date": "2026-08-20",
                        "value": "17.25",
                        "metadata": {"provider": "fred"},
                        "retrieved_at": "2026-08-21T00:00:00+00:00",
                    }
                ],
            )
        if table == "match_evidence_chunks":
            return httpx.Response(
                200,
                json=[
                    {
                        "chunk_id": 4,
                        "document_id": 12,
                        "ticker": "AAPL",
                        "source_type": "filing",
                        "title": "AAPL 10-Q",
                        "url": "https://www.sec.gov/example",
                        "published_at": "2026-02-01T00:00:00+00:00",
                        "chunk_text": "Supply chain risk context.",
                        "metadata": {"source": "SEC EDGAR"},
                        "similarity": 0.75,
                    }
                ],
            )
        if table == "evidence_documents" and request.method == "GET" and "stock_id" in query:
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 12,
                        "external_id": "sec-aapl-example",
                        "source_type": "filing",
                        "title": "AAPL 10-Q filed 2026-02-01",
                        "url": "https://www.sec.gov/example",
                        "published_at": "2026-02-01T00:00:00+00:00",
                        "raw_text": "Live SEC filing metadata.",
                        "metadata": {
                            "source": "SEC EDGAR submissions API",
                            "sections": ["Item 1A — Risk Factors"],
                        },
                        "created_at": "2026-08-13T00:00:00+00:00",
                    }
                ],
            )
        if table == "watchlists" and request.method == "GET":
            return httpx.Response(
                200,
                json=[{"stocks": {"ticker": "AAPL"}}] if self.watchlist else [],
            )
        if table == "watchlists" and request.method == "POST":
            self.watchlist.add(body["stock_id"])
            return httpx.Response(201)
        if table == "watchlists" and request.method == "DELETE":
            self.watchlist.discard(int(query["stock_id"][0].removeprefix("eq.")))
            return httpx.Response(204)
        if table == "analysis_runs" and request.method == "POST":
            self.analysis_ids.append(body["id"])
            return httpx.Response(201)
        if table == "analysis_runs" and request.method == "GET":
            return httpx.Response(200, json=[{"id": item} for item in self.analysis_ids])
        if table == "agent_outputs" and request.method == "POST":
            response_row = next(row for row in body if row["agent_name"] == "response")
            self.responses[response_row["analysis_run_id"]] = response_row["output_json"]
            return httpx.Response(201)
        if table == "agent_outputs" and request.method == "GET":
            analysis_id = query["analysis_run_id"][0].removeprefix("eq.")
            payload = self.responses.get(analysis_id)
            return httpx.Response(200, json=[{"output_json": payload}] if payload else [])
        if table == "token_usage":
            return httpx.Response(201)
        if table == "evidence_documents":
            return httpx.Response(200, json=[])
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")


def build_store(fake: FakePostgrest) -> SupabaseStore:
    client = httpx.Client(transport=httpx.MockTransport(fake))
    return SupabaseStore("https://example.supabase.co", "anon-key", client)


def test_supabase_watchlist_round_trip() -> None:
    fake = FakePostgrest()
    store = build_store(fake)

    assert store.add_watchlist("user-1", "AAPL", "user-token") == ["AAPL"]
    assert store.remove_watchlist("user-1", "AAPL", "user-token") == []


def test_supabase_analysis_round_trip() -> None:
    response = AnalysisService(DemoStore()).create("AAPL")
    fake = FakePostgrest()
    store = build_store(fake)

    store.save_analysis("user-1", response.analysis_id, response, "user-token")

    assert store.get_analysis("user-1", response.analysis_id, "user-token") == response
    assert store.list_analyses("user-1", "user-token") == [response]


def test_supabase_evidence_combines_technical_and_live_documents() -> None:
    fake = FakePostgrest()
    store = build_store(fake)

    evidence = store.get_evidence("AAPL")

    assert any(item["source_type"] == "technical" for item in evidence)
    assert any(item["id"] == "sec-aapl-example" for item in evidence)
    filing = next(item for item in evidence if item["id"] == "sec-aapl-example")
    assert filing["metadata"]["sections"] == ["Item 1A — Risk Factors"]
    assert filing["freshness"]["status"] == "stale"


def test_supabase_search_uses_vector_rpc() -> None:
    fake = FakePostgrest()
    store = build_store(fake)

    evidence = store.search_evidence("AAPL", "supply chain risk")

    assert evidence[0]["id"] == "chunk-4"
    assert evidence[0]["metadata"]["document_id"] == "12"
    assert evidence[0]["freshness"]["status"] == "stale"


def test_supabase_search_falls_back_to_stored_documents_when_vector_rpc_has_no_matches() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
    )
    store = SupabaseStore("https://example.supabase.co", "anon-key", client)

    evidence = store.search_evidence("AAPL", "revenue growth")

    assert evidence
    assert evidence[0]["metadata"]["retrieval_mode"] == "document_fallback"
    assert evidence[0]["metadata"]["fallback_reason"] == "no_vector_matches"
    assert all("demo" not in item["id"].lower() for item in evidence)


def test_supabase_search_falls_back_to_stored_documents_when_vector_rpc_is_unavailable() -> None:
    def vector_search_is_unavailable(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/rpc/match_evidence_chunks"):
            return httpx.Response(503)
        if request.url.path.endswith("/stocks"):
            return httpx.Response(200, json=[{"id": 1}])
        if request.url.path.endswith("/evidence_documents"):
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 12,
                        "external_id": "sec-aapl-example",
                        "source_type": "filing",
                        "title": "AAPL 10-Q filed 2026-02-01",
                        "url": "https://www.sec.gov/example",
                        "published_at": "2026-02-01T00:00:00+00:00",
                        "raw_text": "Risk factor context from a stored SEC filing.",
                        "metadata": {"source": "SEC EDGAR"},
                        "created_at": "2026-08-13T00:00:00+00:00",
                    }
                ],
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = httpx.Client(
        transport=httpx.MockTransport(vector_search_is_unavailable)
    )
    store = SupabaseStore("https://example.supabase.co", "anon-key", client)

    evidence = store.search_evidence("AAPL", "risk factors")

    assert evidence
    assert evidence[0]["metadata"]["retrieval_mode"] == "document_fallback"
    assert evidence[0]["metadata"]["fallback_reason"] == "rpc_unavailable"
    assert all("demo" not in item["id"].lower() for item in evidence)


def test_supabase_prices_include_live_cache_provenance() -> None:
    fake = FakePostgrest()
    fake.price_rows = [
        {
            "trading_date": datetime.now(timezone.utc).date().isoformat(),
            "open": "220.1",
            "high": "224.5",
            "low": "219.0",
            "close": "223.75",
            "volume": 50_123_456,
        }
    ]
    store = build_store(fake)

    prices = store.get_prices("AAPL")

    assert prices[0]["source"] == "daily_market_cache"
    assert prices[0]["is_stale"] is False
    assert prices[0]["close"] == 223.75


def test_supabase_prices_fall_back_when_cache_is_unavailable() -> None:
    fake = FakePostgrest()
    fake.price_status = 503
    store = build_store(fake)

    prices = store.get_prices("AAPL")

    assert prices
    assert all(point["source"] == "demo_fallback" for point in prices)
    assert all(point["is_stale"] is True for point in prices)


def test_supabase_reads_cached_macro_series_and_observations() -> None:
    fake = FakePostgrest()
    store = build_store(fake)

    series = store.get_macro_series()
    observations = store.get_macro_observations("vix")

    assert series[0]["code"] == "vix"
    assert series[0]["metadata"]["provider_series_id"] == "VIXCLS"
    assert observations[0]["value"] == 17.25
