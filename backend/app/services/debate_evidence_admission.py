"""Select citable live evidence without trusting cached freshness labels."""
from datetime import datetime
from urllib.parse import urlsplit

from app.domain.factors import AnalysisEvidenceItem
from app.services.evidence_freshness import classify_evidence_freshness


class LiveEvidenceUnavailable(ValueError):
    """The snapshot lacks current, traceable news or filing evidence."""


def select_live_evidence(ticker: str, rows: list[dict[str, object]], *, captured_at: datetime) -> list[AnalysisEvidenceItem]:
    if captured_at.tzinfo is None or captured_at.utcoffset() is None:
        raise ValueError("Capture time must include a timezone")
    selected: dict[str, AnalysisEvidenceItem] = {}
    for row in rows:
        # Technical factors come from validated closes, never demo evidence.
        if row.get("source_type") not in {"news", "filing"}:
            continue
        try:
            item = AnalysisEvidenceItem.model_validate(row)
            location = urlsplit(item.url or "")
            if (item.ticker != ticker.upper()
                    or item.metadata.get("storage") != "supabase"
                    or not item.metadata.get("document_id")
                    or location.scheme not in {"http", "https"}
                    or not location.hostname or location.username or location.password):
                continue
            freshness = classify_evidence_freshness(item.source_type, item.published_at, now=captured_at)
            if freshness["status"] != "current":
                continue
            item = AnalysisEvidenceItem.model_validate({**item.model_dump(), "freshness": freshness})
        except (ValueError, TypeError):
            continue
        if item.id in selected and selected[item.id] != item:
            raise LiveEvidenceUnavailable("Live Debate evidence contains conflicting document IDs")
        selected[item.id] = item
    if {item.source_type for item in selected.values()} != {"news", "filing"}:
        raise LiveEvidenceUnavailable("Live Debate requires current traceable news and filing evidence")
    return list(selected.values())
