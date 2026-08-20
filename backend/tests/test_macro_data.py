import httpx
import pytest

from app.services.macro_data import (
    EiaClient,
    FredClient,
    MacroDataError,
    MacroSeriesDefinition,
    ingest_macro_context,
)


def test_fred_client_normalizes_numeric_observations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["series_id"] == "VIXCLS"
        assert request.url.params["api_key"] == "fred-key"
        assert request.url.params["sort_order"] == "desc"
        return httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2026-08-19", "value": "17.25"},
                    {"date": "2026-08-20", "value": "."},
                ]
            },
        )

    client = FredClient("fred-key", httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.fetch_observations("VIXCLS") == [
        {
            "series_code": "VIXCLS",
            "source": "fred",
            "observation_date": "2026-08-19",
            "value": 17.25,
            "metadata": {"fred_series_id": "VIXCLS"},
        }
    ]


def test_eia_client_normalizes_energy_observations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/PET.RWTC.D")
        assert request.url.params["api_key"] == "eia-key"
        return httpx.Response(
            200,
            json={
                "response": {
                    "data": [
                        {
                            "period": "2026-08-19",
                            "value": "65.31",
                            "units": "dollars per barrel",
                            "series-description": "WTI spot price",
                        }
                    ]
                }
            },
        )

    client = EiaClient("eia-key", httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.fetch_series("PET.RWTC.D") == [
        {
            "series_code": "PET.RWTC.D",
            "source": "eia",
            "observation_date": "2026-08-19",
            "value": 65.31,
            "metadata": {
                "eia_series_id": "PET.RWTC.D",
                "unit": "dollars per barrel",
                "series_name": "WTI spot price",
            },
        }
    ]


def test_macro_clients_require_their_provider_keys() -> None:
    with pytest.raises(ValueError, match="FRED_API_KEY"):
        FredClient(" ")
    with pytest.raises(ValueError, match="EIA_API_KEY"):
        EiaClient("")


def test_fred_client_rejects_malformed_provider_payload() -> None:
    client = FredClient(
        "fred-key",
        httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={}))),
    )

    with pytest.raises(MacroDataError, match="observations"):
        client.fetch_observations("SP500")


def test_macro_ingestion_keeps_provider_series_separate_from_display_code() -> None:
    definition = MacroSeriesDefinition(
        code="treasury_10y_yield",
        name="10-year Treasury yield",
        source="fred",
        provider_series_id="DGS10",
        unit="percent",
        frequency="daily",
    )

    class FakeWriter:
        def __init__(self) -> None:
            self.definitions: tuple[MacroSeriesDefinition, ...] = ()
            self.rows: list[dict[str, object]] = []

        def upsert_series(self, definitions: tuple[MacroSeriesDefinition, ...]) -> int:
            self.definitions = definitions
            return len(definitions)

        def upsert_observations(
            self,
            _definition: MacroSeriesDefinition,
            observations: list[dict[str, object]],
        ) -> int:
            self.rows.extend(observations)
            return len(observations)

    class FakeFred:
        def fetch_observations(self, series_id: str, *, limit: int) -> list[dict[str, object]]:
            assert series_id == "DGS10"
            assert limit == 120
            return [
                {
                    "series_code": "DGS10",
                    "source": "fred",
                    "observation_date": "2026-08-20",
                    "value": 4.31,
                    "metadata": {"fred_series_id": "DGS10"},
                }
            ]

    class FakeEia:
        def fetch_series(self, series_id: str, *, limit: int) -> list[dict[str, object]]:
            raise AssertionError(f"Unexpected EIA series: {series_id}")

    writer = FakeWriter()
    result = ingest_macro_context(
        writer,  # type: ignore[arg-type]
        FakeFred(),  # type: ignore[arg-type]
        FakeEia(),  # type: ignore[arg-type]
        definitions=(definition,),
        limit_per_series=120,
    )

    assert result == {"series": 1, "observations": 1}
    assert writer.definitions == (definition,)
    assert writer.rows[0]["series_code"] == "DGS10"
