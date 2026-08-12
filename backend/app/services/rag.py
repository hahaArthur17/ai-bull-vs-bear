from __future__ import annotations

import re
from collections.abc import Iterable
from hashlib import sha256
from math import sqrt


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


def local_embedding(text: str, dimensions: int = 1536) -> list[float]:
    """Create a deterministic, credit-free hashed term embedding."""

    if dimensions <= 0:
        raise ValueError("dimensions must be positive")
    vector = [0.0] * dimensions
    for term in _terms(text):
        digest = sha256(term.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % dimensions
        vector[index] += -1.0 if digest[8] & 1 else 1.0
    norm = sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def embedding_literal(vector: Iterable[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
