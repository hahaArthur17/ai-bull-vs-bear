import pytest

from app.services.rag import chunk_text, embedding_literal, local_embedding, retrieve_evidence


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


def test_local_embedding_is_deterministic_and_normalized() -> None:
    first = local_embedding("supply chain risk", dimensions=16)
    second = local_embedding("supply chain risk", dimensions=16)

    assert first == second
    assert abs(sum(value * value for value in first) - 1.0) < 1e-8
    assert embedding_literal(first).startswith("[")
