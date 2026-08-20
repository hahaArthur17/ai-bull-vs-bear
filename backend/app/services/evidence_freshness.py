"""Classify whether evidence is recent enough for a current-price discussion."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal


FreshnessStatus = Literal["current", "stale", "unknown"]

# These are deliberately source-specific. A filing remains useful context for
# longer than a news report, but neither should silently stand in for current
# company news.
FRESHNESS_WINDOWS_DAYS: dict[str, int] = {
    "news": 7,
    "filing": 120,
}


def classify_evidence_freshness(
    source_type: str,
    published_at: str | None,
    *,
    now: datetime | None = None,
) -> dict[str, object]:
    """Return a serializable freshness assessment for one evidence document."""

    evaluated_at = now or datetime.now(timezone.utc)
    if evaluated_at.tzinfo is None:
        evaluated_at = evaluated_at.replace(tzinfo=timezone.utc)
    window_days = FRESHNESS_WINDOWS_DAYS.get(source_type)
    if window_days is None or not published_at:
        return {
            "status": "unknown",
            "age_days": None,
            "max_age_days": window_days,
            "evaluated_at": evaluated_at.isoformat(),
        }
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return {
            "status": "unknown",
            "age_days": None,
            "max_age_days": window_days,
            "evaluated_at": evaluated_at.isoformat(),
        }
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    age_days = max((evaluated_at.date() - published.date()).days, 0)
    return {
        "status": "current" if age_days <= window_days else "stale",
        "age_days": age_days,
        "max_age_days": window_days,
        "evaluated_at": evaluated_at.isoformat(),
    }


def is_current_for_analysis(item: dict[str, object]) -> bool:
    """Keep technical observations and only timely external context in Debate."""

    if item.get("source_type") == "technical":
        return True
    freshness = item.get("freshness")
    return isinstance(freshness, dict) and freshness.get("status") == "current"
