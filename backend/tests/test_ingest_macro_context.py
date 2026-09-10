import pytest

from app.services.macro_data import DEFAULT_MACRO_SERIES
from scripts import ingest_macro_context as macro_script
from scripts.ingest_macro_context import (
    DEFAULT_PROVIDER_REQUEST_BUDGET,
    macro_provider_request_budget,
    parse_args,
    select_macro_series,
)


def test_macro_series_selector_defaults_to_all_series_and_counts_each_request() -> None:
    selected = select_macro_series(None)

    assert selected == DEFAULT_MACRO_SERIES
    assert macro_provider_request_budget(selected) == DEFAULT_PROVIDER_REQUEST_BUDGET == 7


def test_macro_series_selector_rejects_unknown_or_empty_selection() -> None:
    with pytest.raises(SystemExit):
        parse_args(["--series", "unknown_series"])
    with pytest.raises(SystemExit):
        parse_args(["--series", ""])
    with pytest.raises(ValueError, match="at least one"):
        select_macro_series([])


def test_wti_only_selection_makes_one_eia_request_and_no_fred_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeWriter:
        def __init__(self) -> None:
            self.definitions = ()
            self.observations: list[dict[str, object]] = []

        def upsert_series(self, definitions):
            self.definitions = definitions
            return len(definitions)

        def upsert_observations(self, _definition, observations):
            self.observations.extend(observations)
            return len(observations)

    class FakeFred:
        def __init__(self) -> None:
            raise AssertionError("WTI-only refresh must not construct FRED")

    class FakeEia:
        def __init__(self, _api_key: str) -> None:
            self.calls: list[tuple[str, int]] = []

        def fetch_series(self, series_id: str, *, limit: int):
            self.calls.append((series_id, limit))
            return [
                {
                    "series_code": series_id,
                    "source": "eia",
                    "observation_date": "2026-09-09",
                    "value": 65.31,
                    "metadata": {"eia_series_id": series_id},
                }
            ]

    writer = FakeWriter()
    eia = FakeEia("eia-key")

    class FakeSettings:
        supabase_url = "https://supabase.example"
        supabase_secret_key = "service-key"
        fred_api_key = None
        eia_api_key = "eia-key"
        macro_history_points = 400

    monkeypatch.setattr(macro_script, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(macro_script, "MacroDataWriter", lambda *_args: writer)
    monkeypatch.setattr(macro_script, "FredClient", FakeFred)
    monkeypatch.setattr(macro_script, "EiaClient", lambda api_key: eia)

    macro_script.main(["--series", "wti_spot"])

    assert macro_provider_request_budget(select_macro_series(["wti_spot"])) == 1
    assert eia.calls == [("PET.RWTC.D", 400)]
    assert writer.definitions == select_macro_series(["wti_spot"])
