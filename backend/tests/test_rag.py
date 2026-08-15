import pytest

from app.services.rag import build_evidence_chunks, chunk_text, retrieve_evidence


def test_chunk_text_preserves_overlap() -> None:
    chunks = chunk_text("one two three four five six", chunk_size=4, overlap=1)
    assert chunks == ["one two three four", "four five six"]


def test_retrieve_evidence_prioritises_query_matches() -> None:
    documents = [
        {"id": "risk", "title": "Supply chain risk", "excerpt": "Execution uncertainty", "source_type": "filing"},
        {"id": "news", "title": "Services growth", "excerpt": "Positive business context", "source_type": "news"},
    ]
    result = retrieve_evidence(documents, "supply chain risk")
    assert result[0]["id"] == "risk"


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        chunk_text("hello world", chunk_size=3, overlap=3)


def test_news_chunks_include_deterministic_article_context() -> None:
    chunks = build_evidence_chunks(
        text="Revenue rose strongly. Demand remained resilient.",
        title="Quarterly revenue update",
        ticker="nvda",
        source_type="news",
        published_at="2026-08-15T02:30:00Z",
        chunk_size=5,
        overlap=1,
    )

    assert chunks[0]["chunk_text"].startswith(
        "NVDA | news | 2026-08-15 | Quarterly revenue update\n"
    )
    assert chunks[0]["metadata"]["chunk_kind"] == "news_paragraph_group"
    assert len(chunks[0]["metadata"]["content_hash"]) == 64


def test_filing_chunks_preserve_section_and_reporting_period() -> None:
    chunks = build_evidence_chunks(
        text=(
            "Item 1A — Risk Factors\nSupply constraints may affect margins.\n\n"
            "Item 7 — Management's Discussion and Analysis\n"
            "Revenue rose while operating costs increased."
        ),
        title="AAPL 10-K filed 2026-08-01",
        ticker="AAPL",
        source_type="filing",
        published_at="2026-08-01",
        metadata={
            "form": "10-K",
            "report_date": "2026-06-30",
            "sections": [
                "Item 1A — Risk Factors",
                "Item 7 — Management's Discussion and Analysis",
            ],
        },
        chunk_size=20,
        overlap=2,
    )

    assert len(chunks) == 2
    assert chunks[0]["metadata"]["section_path"] == "Item 1A — Risk Factors"
    assert chunks[0]["chunk_text"].startswith(
        "AAPL | filing | 2026-06-30 | 10-K | AAPL 10-K filed 2026-08-01 | "
        "Item 1A — Risk Factors\n"
    )
    assert chunks[1]["metadata"]["chunk_kind"] == "filing_section"
