from datetime import datetime, timedelta, timezone

import pytest

from app.services.debate_evidence_admission import LiveEvidenceUnavailable, select_live_evidence
from app.services.evidence_freshness import classify_evidence_freshness

NOW = datetime(2026, 9, 9, 12, tzinfo=timezone.utc)


def document(kind, days=0, **changes):
    return dict(dict(id=kind, ticker="AAPL", source_type=kind, title="Document", excerpt="Dated fact",
        url="https://example.com/document", published_at=(NOW-timedelta(days=days)).isoformat(),
        metadata={"storage": "supabase", "document_id": kind}, freshness={"status": "current"}), **changes)


def test_source_windows_are_recomputed_and_obsolete_rows_are_not_citable():
    rows = [document("news", 7), document("filing", 120), document("news", 8, id="old")]
    result = select_live_evidence("aapl", rows, captured_at=NOW)
    assert [item.id for item in result] == ["news", "filing"]
    assert result[0].freshness.age_days == 7
    assert result[1].freshness.max_age_days == 120
    assert rows[0]["freshness"] == {"status": "current"}


@pytest.mark.parametrize("changes", [
    {"published_at": "bad-date"}, {"published_at": "2099-01-01"},
    {"published_at": (NOW+timedelta(seconds=1)).isoformat()},
    {"metadata": {}}, {"ticker": "MSFT"}, {"url": "javascript:alert(1)"},
    {"url": "https://"}, {"url": "https://user:secret@example.com"},
])
def test_missing_valid_news_fails_closed(changes):
    with pytest.raises(LiveEvidenceUnavailable):
        select_live_evidence("AAPL", [document("news", **changes), document("filing")], captured_at=NOW)


def test_conflicting_ids_fail_and_exact_duplicates_are_deduplicated():
    rows = [document("news"), document("filing")]
    assert len(select_live_evidence("AAPL", rows+[rows[0]], captured_at=NOW)) == 2
    with pytest.raises(LiveEvidenceUnavailable, match="conflicting"):
        select_live_evidence("AAPL", rows+[document("news", excerpt="Different")], captured_at=NOW)


def test_future_date_is_unknown_even_with_same_calendar_day():
    assert classify_evidence_freshness("news", (NOW+timedelta(seconds=1)).isoformat(), now=NOW)["status"] == "unknown"
