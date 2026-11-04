"""Select date-eligible evidence while preserving retrieval order and source coverage."""

from dataclasses import dataclass

from app.schemas import EvidenceItem
from app.services.demo_store import DemoStore
from app.services.evidence_freshness import is_current_for_analysis
from app.services.rag import retrieve_evidence


@dataclass(frozen=True)
class SelectedAnalysisEvidence:
    items: list[EvidenceItem]
    retrieved_count: int
    excluded_stale_count: int
    supplemented_count: int

    @property
    def external_types(self) -> set[str]:
        return {item.source_type for item in self.items if item.source_type != "technical"}

    def fallback_ids(self, side: str) -> list[str]:
        """Prefer a technical observation and one source from the ranked set."""
        technical_ids = [item.id for item in self.items if item.source_type == "technical"]
        if side == "bull":
            return list(dict.fromkeys(technical_ids[:1] + [item.id for item in self.items[:1]]))
        return list(dict.fromkeys(technical_ids[-1:] + [item.id for item in self.items[-1:]]))


def select_analysis_evidence(
    store: DemoStore, ticker: str, question: str
) -> SelectedAnalysisEvidence:
    """Exclude stale external sources, then fill at most one missing source per kind."""
    evidence_query = question
    search_evidence = getattr(store, "search_evidence", None)
    raw_evidence = (
        search_evidence(ticker, evidence_query)
        if callable(search_evidence)
        else retrieve_evidence(store.get_evidence(ticker), evidence_query)
    )
    retrieved_evidence = [EvidenceItem.model_validate(item) for item in raw_evidence]
    evidence = [item for item in retrieved_evidence if is_current_for_analysis(item.model_dump())]
    excluded_stale_count = len(retrieved_evidence) - len(evidence)
    supplemented_evidence: list[EvidenceItem] = []
    # Similarity retrieval can legitimately rank several filing chunks above
    # a fresh company announcement. For a current-price discussion, retain
    # that relevant ranking but ensure that at most one *current* document
    # from each external source category is also available to the Debate.
    all_documents = [EvidenceItem.model_validate(item) for item in store.get_evidence(ticker)]
    for source_type in ("news", "filing"):
        if any(item.source_type == source_type for item in evidence):
            continue
        candidate = next(
            (
                item
                for item in sorted(
                    all_documents,
                    key=lambda value: value.published_at or "",
                    reverse=True,
                )
                if item.source_type == source_type
                and is_current_for_analysis(item.model_dump())
                and item.id not in {existing.id for existing in evidence}
            ),
            None,
        )
        if candidate is not None:
            evidence.append(candidate)
            supplemented_evidence.append(candidate)
    if not any(item.source_type == "technical" for item in evidence):
        technical_candidate = next(
            (item for item in all_documents if item.source_type == "technical"),
            None,
        )
        if technical_candidate is not None:
            evidence.insert(0, technical_candidate)
            supplemented_evidence.append(technical_candidate)
    return SelectedAnalysisEvidence(
        items=evidence,
        retrieved_count=len(retrieved_evidence) + len(supplemented_evidence),
        excluded_stale_count=excluded_stale_count,
        supplemented_count=len(supplemented_evidence),
    )
