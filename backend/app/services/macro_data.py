"""Small, cache-oriented clients for free macro-economic time series."""

from __future__ import annotations

from typing import Any

import httpx


class MacroDataError(RuntimeError):
    pass


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
