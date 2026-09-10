#!/usr/bin/env python3
"""Fetch one bounded macro context history and write it to Supabase."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from app.config import get_settings
from app.services.macro_data import (
    DEFAULT_MACRO_SERIES,
    EiaClient,
    FredClient,
    MacroDataWriter,
    MacroSeriesDefinition,
    ingest_macro_context,
)


DEFAULT_PROVIDER_REQUEST_BUDGET = len(DEFAULT_MACRO_SERIES)
_SERIES_BY_CODE = {definition.code: definition for definition in DEFAULT_MACRO_SERIES}


def select_macro_series(
    selections: Sequence[str] | None,
) -> tuple[MacroSeriesDefinition, ...]:
    """Resolve explicit display-code selectors without silently broadening scope."""

    if selections is None:
        return DEFAULT_MACRO_SERIES
    if not selections:
        raise ValueError("at least one macro series must be selected")

    requested_codes: list[str] = []
    for selection in selections:
        if not isinstance(selection, str):
            raise ValueError("macro series selection must be a string")
        # Comma-separated values make this usable from shell jobs that already
        # represent lists this way, while repeated --series values stay clear.
        codes = selection.split(",")
        if any(not code.strip() for code in codes):
            raise ValueError("macro series selection cannot be empty")
        requested_codes.extend(code.strip() for code in codes)

    unknown_codes = sorted(set(requested_codes) - _SERIES_BY_CODE.keys())
    if unknown_codes:
        raise ValueError(f"unknown macro series: {', '.join(unknown_codes)}")

    if len(requested_codes) != len(set(requested_codes)):
        raise ValueError("macro series selections must be unique")

    return tuple(_SERIES_BY_CODE[code] for code in requested_codes)


def macro_provider_request_budget(
    definitions: Sequence[MacroSeriesDefinition],
) -> int:
    """Return the exact number of upstream requests the core ingestion makes."""

    if not definitions:
        raise ValueError("at least one macro series must be selected")
    if any(definition.source not in {"fred", "eia"} for definition in definitions):
        raise ValueError("unsupported macro provider in selected series")
    budget = len(definitions)
    if budget > DEFAULT_PROVIDER_REQUEST_BUDGET:
        raise ValueError("macro provider request budget exceeded")
    return budget


class _ProviderRequestBudget:
    """Count and cap the provider calls made by one ingestion invocation."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0

    def consume(self) -> None:
        if self.used >= self.limit:
            raise RuntimeError("macro provider request budget exceeded")
        self.used += 1

    def verify(self) -> None:
        if self.used != self.limit:
            raise RuntimeError(
                "macro provider request count did not match selected series"
            )


class _BudgetedFredClient:
    def __init__(self, client: FredClient, budget: _ProviderRequestBudget) -> None:
        self._client = client
        self._budget = budget

    def fetch_observations(self, series_id: str, *, limit: int) -> list[dict[str, object]]:
        self._budget.consume()
        return self._client.fetch_observations(series_id, limit=limit)


class _BudgetedEiaClient:
    def __init__(self, client: EiaClient, budget: _ProviderRequestBudget) -> None:
        self._client = client
        self._budget = budget

    def fetch_series(self, series_id: str, *, limit: int) -> list[dict[str, object]]:
        self._budget.consume()
        return self._client.fetch_series(series_id, limit=limit)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--series",
        action="append",
        metavar="CODE[,CODE...]",
        help=(
            "Refresh only the selected macro display code(s); repeat the option "
            "or use comma-separated values. Defaults to all configured series."
        ),
    )
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        select_macro_series(args.series)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    definitions = select_macro_series(args.series)
    provider_request_budget = macro_provider_request_budget(definitions)

    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SECRET_KEY are required")

    requires_fred = any(definition.source == "fred" for definition in definitions)
    requires_eia = any(definition.source == "eia" for definition in definitions)
    if args.series is None and (not settings.fred_api_key or not settings.eia_api_key):
        # Keep the legacy all-series error and credential requirements intact.
        raise SystemExit("FRED_API_KEY and EIA_API_KEY are required")
    if requires_fred and not settings.fred_api_key:
        raise SystemExit("FRED_API_KEY is required for the selected macro series")
    if requires_eia and not settings.eia_api_key:
        raise SystemExit("EIA_API_KEY is required for the selected macro series")

    # A provider client is only constructed for a selected source. Count the
    # calls at the client boundary so a future core change cannot overspend or
    # silently under-refresh the selected request budget.
    request_budget = _ProviderRequestBudget(provider_request_budget)
    fred = (
        _BudgetedFredClient(FredClient(settings.fred_api_key), request_budget)
        if requires_fred and settings.fred_api_key
        else None
    )
    eia = (
        _BudgetedEiaClient(EiaClient(settings.eia_api_key), request_budget)
        if requires_eia and settings.eia_api_key
        else None
    )
    result = ingest_macro_context(
        MacroDataWriter(settings.supabase_url, settings.supabase_secret_key),
        fred,  # type: ignore[arg-type]
        eia,  # type: ignore[arg-type]
        definitions=definitions,
        limit_per_series=settings.macro_history_points,
    )
    request_budget.verify()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
