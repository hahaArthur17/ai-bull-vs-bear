from datetime import datetime, timezone

from app.services.evidence_freshness import (
    classify_evidence_freshness,
    is_current_for_analysis,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def test_classifies_recent_news_as_current() -> None:
    freshness = classify_evidence_freshness("news", "2026-08-15T09:00:00Z", now=NOW)

    assert freshness["status"] == "current"
    assert freshness["age_days"] == 6
    assert freshness["max_age_days"] == 7


def test_classifies_old_news_as_stale() -> None:
    freshness = classify_evidence_freshness("news", "2026-08-13", now=NOW)

    assert freshness["status"] == "stale"
    assert freshness["age_days"] == 8


def test_classifies_filing_with_a_longer_context_window() -> None:
    freshness = classify_evidence_freshness("filing", "2026-07-31", now=NOW)

    assert freshness["status"] == "current"
    assert freshness["max_age_days"] == 120


def test_missing_or_invalid_dates_are_unknown() -> None:
    assert classify_evidence_freshness("news", None, now=NOW)["status"] == "unknown"
    assert classify_evidence_freshness("news", "not-a-date", now=NOW)["status"] == "unknown"


def test_only_current_external_evidence_is_eligible_for_analysis() -> None:
    assert is_current_for_analysis({"source_type": "technical"}) is True
    assert is_current_for_analysis({"source_type": "news", "freshness": {"status": "current"}}) is True
    assert is_current_for_analysis({"source_type": "news", "freshness": {"status": "stale"}}) is False
    assert is_current_for_analysis({"source_type": "filing"}) is False
