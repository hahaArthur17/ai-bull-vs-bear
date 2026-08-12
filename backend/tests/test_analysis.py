from app.services.analysis import AnalysisService
from app.services.demo_store import DemoStore


def test_analysis_contains_bull_bear_evidence_and_trace() -> None:
    service = AnalysisService(DemoStore())
    response = service.create("AAPL")
    assert response.ticker == "AAPL"
    assert response.bull.evidence_ids
    assert response.bear.evidence_ids
    assert {item.id for item in response.evidence} >= set(response.bull.evidence_ids + response.bear.evidence_ids)
    assert len(response.trace) == 8
    examined = service.examine(response.bull.id, "evidence_support")
    assert examined.evidence


def test_analysis_history_is_isolated_by_user() -> None:
    service = AnalysisService(DemoStore())
    response = service.create("AAPL", user_id="user-a")

    assert service.get(response.analysis_id, user_id="user-a") == response
    assert service.get(response.analysis_id, user_id="user-b") is None
