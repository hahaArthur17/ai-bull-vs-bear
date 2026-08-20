"""Small, cache-oriented clients for free macro-economic time series."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.services.supabase_headers import service_headers


class MacroDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class MacroSeriesDefinition:
    code: str
    name: str
    source: str
    provider_series_id: str
    unit: str
    frequency: str


DEFAULT_MACRO_SERIES = (
    MacroSeriesDefinition("sp500", "S&P 500 close", "fred", "SP500", "index points", "daily"),
    MacroSeriesDefinition("vix", "CBOE Volatility Index", "fred", "VIXCLS", "index points", "daily"),
    MacroSeriesDefinition(
        "effective_fed_funds_rate",
        "Effective federal funds rate",
        "fred",
        "EFFR",
        "percent",
        "daily",
    ),
    MacroSeriesDefinition("treasury_2y_yield", "2-year Treasury yield", "fred", "DGS2", "percent", "daily"),
    MacroSeriesDefinition("treasury_10y_yield", "10-year Treasury yield", "fred", "DGS10", "percent", "daily"),
    MacroSeriesDefinition("treasury_30y_yield", "30-year Treasury yield", "fred", "DGS30", "percent", "daily"),
    MacroSeriesDefinition("wti_spot", "WTI crude oil spot price", "eia", "PET.RWTC.D", "USD/barrel", "daily"),
)


class FredClient:
    base_url = "https://api.stlouisfed.org/fred/series/observations"

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key.strip():
            raise ValueError("FRED_API_KEY is required")
        self.api_key = api_key
        self.client = client

    def fetch_observations(
        self,
        series_id: str,
        *,
        limit: int = 400,
    ) -> list[dict[str, object]]:
        try:
            requester = self.client.get if self.client is not None else httpx.get
            response = requester(
                self.base_url,
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": str(limit),
                },
                timeout=15.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MacroDataError(f"FRED request failed for {series_id}") from exc
        payload = response.json()
        observations = payload.get("observations")
        if not isinstance(observations, list):
            raise MacroDataError(f"FRED response for {series_id} did not include observations")
        parsed: list[dict[str, object]] = []
        for observation in observations:
            if not isinstance(observation, dict):
                continue
            date = observation.get("date")
            raw_value = observation.get("value")
            if not isinstance(date, str) or raw_value in {None, "."}:
                continue
            try:
                value = float(str(raw_value))
            except ValueError:
                continue
            parsed.append(
                {
                    "series_code": series_id,
                    "source": "fred",
                    "observation_date": date,
                    "value": value,
                    "metadata": {"fred_series_id": series_id},
                }
            )
        return sorted(parsed, key=lambda item: str(item["observation_date"]))


class EiaClient:
    base_url = "https://api.eia.gov/v2/seriesid"

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        if not api_key.strip():
            raise ValueError("EIA_API_KEY is required")
        self.api_key = api_key
        self.client = client

    def fetch_series(self, series_id: str, *, limit: int = 400) -> list[dict[str, object]]:
        try:
            requester = self.client.get if self.client is not None else httpx.get
            response = requester(
                f"{self.base_url}/{series_id}",
                params={"api_key": self.api_key, "length": str(limit)},
                timeout=15.0,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MacroDataError(f"EIA request failed for {series_id}") from exc
        payload = response.json()
        response_data = payload.get("response")
        rows = response_data.get("data") if isinstance(response_data, dict) else None
        if not isinstance(rows, list):
            raise MacroDataError(f"EIA response for {series_id} did not include data")
        parsed: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            period = row.get("period")
            raw_value = row.get("value")
            if not isinstance(period, str) or raw_value in {None, "."}:
                continue
            try:
                value = float(str(raw_value))
            except ValueError:
                continue
            metadata: dict[str, Any] = {
                "eia_series_id": series_id,
                "unit": row.get("units"),
                "series_name": row.get("series-description"),
            }
            parsed.append(
                {
                    "series_code": series_id,
                    "source": "eia",
                    "observation_date": period,
                    "value": value,
                    "metadata": {key: value for key, value in metadata.items() if value is not None},
                }
            )
        return sorted(parsed, key=lambda item: str(item["observation_date"]))


class MacroDataWriter:
    """Persist the public, cacheable macro series with a server-only key."""

    def __init__(
        self,
        supabase_url: str,
        secret_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.rest_url = f"{supabase_url.rstrip('/')}/rest/v1"
        self.secret_key = secret_key
        self.client = client

    def _request(self, method: str, table: str, **kwargs: object) -> httpx.Response:
        requester = self.client.request if self.client is not None else httpx.request
        response = requester(
            method,
            f"{self.rest_url}/{table}",
            headers=service_headers(
                self.secret_key,
                str(kwargs.pop("prefer", "return=minimal")),
            ),
            timeout=15.0,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def upsert_series(self, definitions: tuple[MacroSeriesDefinition, ...]) -> int:
        payload = [
            {
                "code": definition.code,
                "name": definition.name,
                "source": definition.source,
                "unit": definition.unit,
                "frequency": definition.frequency,
                "metadata": {"provider_series_id": definition.provider_series_id},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            for definition in definitions
        ]
        if not payload:
            return 0
        self._request(
            "POST",
            "macro_series",
            params={"on_conflict": "code"},
            json=payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )
        return len(payload)

    def upsert_observations(
        self,
        definition: MacroSeriesDefinition,
        observations: list[dict[str, object]],
    ) -> int:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        payload = [
            {
                "series_code": definition.code,
                "observation_date": str(observation["observation_date"]).split("T", 1)[0],
                "value": observation["value"],
                "metadata": {
                    **(
                        observation["metadata"]
                        if isinstance(observation.get("metadata"), dict)
                        else {}
                    ),
                    "provider": definition.source,
                    "provider_series_id": definition.provider_series_id,
                },
                "retrieved_at": retrieved_at,
            }
            for observation in observations
        ]
        if not payload:
            return 0
        self._request(
            "POST",
            "macro_observations",
            params={"on_conflict": "series_code,observation_date"},
            json=payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )
        return len(payload)


def ingest_macro_context(
    writer: MacroDataWriter,
    fred: FredClient,
    eia: EiaClient,
    definitions: tuple[MacroSeriesDefinition, ...] = DEFAULT_MACRO_SERIES,
    *,
    limit_per_series: int = 400,
) -> dict[str, int]:
    """Fetch one bounded history per series, then upsert it into the cache."""

    series_written = writer.upsert_series(definitions)
    observation_count = 0
    for definition in definitions:
        if definition.source == "fred":
            observations = fred.fetch_observations(
                definition.provider_series_id,
                limit=limit_per_series,
            )
        elif definition.source == "eia":
            observations = eia.fetch_series(
                definition.provider_series_id,
                limit=limit_per_series,
            )
        else:
            raise ValueError(f"Unsupported macro source: {definition.source}")
        observation_count += writer.upsert_observations(definition, observations)
    return {"series": series_written, "observations": observation_count}
