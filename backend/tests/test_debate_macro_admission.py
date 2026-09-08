from copy import deepcopy
from datetime import datetime, timezone

import pytest

from app.services.macro_data import DEFAULT_MACRO_SERIES
from app.services.debate_macro_admission import LiveMacroUnavailable, require_live_macro_context

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def rows():
    return [dict(code=d.code, name=d.name, source=d.source, unit=d.unit, value=1,
                 observation_date="2026-09-08", retrieved_at="2026-09-09T10:00:00Z",
                 metadata={"provider": d.source, "provider_series_id": d.provider_series_id})
            for d in DEFAULT_MACRO_SERIES]


def check(data):
    return require_live_macro_context(data, captured_at=NOW, completed_through="2026-09-08")


def test_complete_series_are_ordered_without_mutating_input():
    data = list(reversed(rows()))
    original = deepcopy(data)
    assert [item["code"] for item in check(data)] == [d.code for d in DEFAULT_MACRO_SERIES]
    assert data == original


@pytest.mark.parametrize("field,value", [
    ("source", "wrong"), ("unit", "wrong"), ("metadata", {}),
    ("observation_date", "invalid"), ("observation_date", "2026-09-09"),
    ("observation_date", "2026-09-01"), ("value", float("nan")),
    ("retrieved_at", "2026-09-09T13:00:00Z"), ("retrieved_at", "2026-09-09T10:00:00"),
    ("retrieved_at", "2026-09-01T10:00:00Z"),
])
def test_invalid_or_stale_series_fail_closed(field, value):
    data = rows()
    data[0][field] = value
    with pytest.raises(LiveMacroUnavailable):
        check(data)


def test_missing_and_duplicate_required_codes_fail():
    for data in (rows()[:-1], rows()+[rows()[0]], [rows()[0]]*7):
        with pytest.raises(LiveMacroUnavailable):
            check(data)


def test_seven_day_observation_boundary_is_inclusive():
    data = rows()
    data[0]["observation_date"] = "2026-09-02"
    assert len(check(data)) == 7
