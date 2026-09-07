from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlsplit

from app.debate_schemas import (
    DebateEvidencePresentation,
    DebateMessagePresentation,
)
from app.domain.debate import DebateMessage, DebateMessageEvidence
from app.domain.factors import AnalysisContext, AnalysisEvidenceItem


def _optional_text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def safe_source_destination(value: str | None) -> str | None:
    """Expose only public absolute HTTPS destinations without credentials."""

    if value is None or value != value.strip() or any(char.isspace() for char in value):
        return None
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError:
        return None
    hostname = parsed.hostname.lower() if parsed.hostname else ""
    if (
        parsed.scheme.lower() != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or hostname == "localhost"
        or hostname.endswith((".localhost", ".local", ".internal"))
    ):
        return None
    try:
        address = ip_address(hostname)
    except ValueError:
        pass
    else:
        if not address.is_global:
            return None
    return value


def _evidence_detail(
    citation: DebateMessageEvidence,
    item: AnalysisEvidenceItem | None,
) -> DebateEvidencePresentation:
    if item is None:
        return DebateEvidencePresentation(
            evidence_id=citation.evidence_id,
            support_span=citation.support_span,
            missing_metadata=(
                "evidence_type",
                "title",
                "fact",
                "source",
                "date",
                *(("support_span",) if citation.support_span is None else ()),
                "source_destination",
            ),
        )

    source = _optional_text(item.metadata.get("source"))
    destination = safe_source_destination(item.url)
    missing: list[str] = []
    if source is None:
        missing.append("source")
    if item.published_at is None:
        missing.append("date")
    if citation.support_span is None:
        missing.append("support_span")
    if destination is None:
        missing.append("source_destination")
    return DebateEvidencePresentation(
        evidence_id=citation.evidence_id,
        evidence_type=item.source_type,
        title=item.title,
        fact=item.excerpt,
        source=source,
        date=item.published_at,
        freshness=item.freshness,
        support_span=citation.support_span,
        source_destination=destination,
        missing_metadata=tuple(missing),
    )


def _metadata_text(message: DebateMessage, key: str) -> str | None:
    return _optional_text(message.metadata.get(key))


def build_debate_message_presentation(
    message: DebateMessage,
    citations: tuple[DebateMessageEvidence, ...],
    analysis_context: AnalysisContext,
) -> DebateMessagePresentation:
    """Project renderable facts only from one immutable canonical snapshot."""

    evidence_by_id = {item.id: item for item in analysis_context.evidence}
    facts_used = tuple(
        _evidence_detail(citation, evidence_by_id.get(citation.evidence_id))
        for citation in sorted(citations, key=lambda citation: citation.citation_order)
    )
    uncertainty = _metadata_text(message, "risk_meaning") or _metadata_text(
        message,
        "uncertainty",
    )
    return DebateMessagePresentation(
        argument=message.content,
        facts_used=facts_used,
        interpretation=_metadata_text(message, "interpretation"),
        uncertainty=uncertainty,
    )
