from __future__ import annotations

import re
from collections.abc import Iterable
from hashlib import sha256


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "what",
    "with",
}


def chunk_text(text: str, chunk_size: int = 120, overlap: int = 20) -> list[str]:
    """Split evidence into overlapping word chunks for later embedding."""

    words = text.split()
    if not words:
        return []
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("chunk_size must be positive and overlap must be smaller than chunk_size")
    chunks: list[str] = []
    step = chunk_size - overlap
    for start in range(0, len(words), step):
        chunk = " ".join(words[start : start + chunk_size]).strip()
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks


def _filing_sections(
    text: str,
    section_titles: list[str],
) -> list[tuple[str | None, str]]:
    positions = [
        (position, title)
        for title in section_titles
        if (position := text.find(f"{title}\n")) >= 0
    ]
    if not positions:
        return [(None, text)]
    positions.sort()
    sections: list[tuple[str | None, str]] = []
    for index, (start, title) in enumerate(positions):
        content_start = start + len(title)
        content_end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
        content = text[content_start:content_end].strip()
        if content:
            sections.append((title, content))
    return sections or [(None, text)]


def build_evidence_chunks(
    *,
    text: str,
    title: str,
    ticker: str,
    source_type: str,
    published_at: str | None = None,
    metadata: dict[str, object] | None = None,
    chunk_size: int | None = None,
    overlap: int | None = None,
) -> list[dict[str, object]]:
    """Build source-aware chunks with deterministic document context."""

    source_metadata = metadata or {}
    default_sizes = {
        "news": (260, 30),
        "filing": (420, 50),
        "technical": (180, 20),
    }
    default_size, default_overlap = default_sizes.get(source_type, (220, 30))
    selected_size = chunk_size if chunk_size is not None else default_size
    selected_overlap = overlap if overlap is not None else default_overlap

    raw_sections = source_metadata.get("sections")
    section_titles = (
        [str(item) for item in raw_sections]
        if source_type == "filing" and isinstance(raw_sections, list)
        else []
    )
    segments = _filing_sections(text, section_titles) if section_titles else [(None, text)]
    date_context = str(source_metadata.get("report_date") or published_at or "date unknown")[:10]
    form = str(source_metadata.get("form") or "").strip()
    results: list[dict[str, object]] = []
    for section_title, section_text in segments:
        for body in chunk_text(section_text, selected_size, selected_overlap):
            context_parts = [ticker.upper(), source_type, date_context]
            if form:
                context_parts.append(form)
            context_parts.append(title.strip())
            if section_title:
                context_parts.append(section_title)
            context_header = " | ".join(context_parts)
            contextual_text = f"{context_header}\n{body}"
            results.append(
                {
                    "chunk_text": contextual_text,
                    "metadata": {
                        "chunk_kind": (
                            "filing_section"
                            if source_type == "filing"
                            else "news_paragraph_group"
                            if source_type == "news"
                            else "text"
                        ),
                        "section_path": section_title or title.strip(),
                        "context_header": context_header,
                        "word_count": len(body.split()),
                        "content_hash": sha256(body.encode("utf-8")).hexdigest(),
                    },
                }
            )
    return results


def _terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", text.lower())
        if term not in STOPWORDS and len(term) > 2
    }


def score_evidence(item: dict[str, object], query: str) -> float:
    query_terms = _terms(query)
    if not query_terms:
        return 0.0
    title_terms = _terms(str(item.get("title", "")))
    excerpt_terms = _terms(str(item.get("excerpt", "")))
    source_terms = _terms(str(item.get("source_type", "")))
    return (
        len(query_terms & title_terms) * 4
        + len(query_terms & excerpt_terms) * 2
        + len(query_terms & source_terms)
    )


def retrieve_evidence(
    documents: Iterable[dict[str, object]],
    query: str,
    limit: int = 6,
) -> list[dict[str, object]]:
    scored = [(score_evidence(document, query), index, document) for index, document in enumerate(documents)]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [document.copy() for _, _, document in scored[:limit]]
