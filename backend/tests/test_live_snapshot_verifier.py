from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import importlib.util
from pathlib import Path

from app.domain.factors import AnalysisContext
from app.providers.current_factors import build_current_factor_registry
from app.services.indicators import calculate_indicators

spec = importlib.util.spec_from_file_location("verify_live_snapshot", Path(__file__).resolve().parents[2] / "scripts/verify_live_snapshot.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def capture():
    prices = [dict(date=(date(2026, 5, 1) + timedelta(days=i)).isoformat(),
                   open=100, high=102, low=99, close=101, volume=100,
                   source="daily_market_cache", is_stale=False) for i in range(50)]
    quote = dict(ticker="AAPL", close=102, open=101, high=103, low=100,
                 previous_close=101, as_of="2026-06-19T20:00:00+00:00", source="finnhub_quote")
    evidence = [dict(id="e1", ticker="AAPL", source_type="news", title="News",
                     url="https://example.com/news", published_at="2026-06-19",
                     excerpt="A dated observation.", freshness={"status": "current"})]
    macro = [dict(code=f"series-{i}", name="Series", source="fred", unit="percent",
                  observation_date="2026-06-01", retrieved_at="2026-06-19T20:00:00Z", value=1)
             for i in range(7)]
    context = AnalysisContext(ticker="AAPL", as_of=prices[-1]["date"],
        captured_at="2026-06-19T20:20:00Z", latest_completed_close_date=prices[-1]["date"],
        market_quote={**quote, "retrieved_at": "2026-06-19T20:00:30Z", "freshness": {"status": "current"}},
        prices=prices, evidence=evidence, allowed_evidence_ids={"e1"}, macro_context=macro)
    snapshot = build_current_factor_registry().collect(context)
    return {"session": {"analysis_context": context.model_dump(mode="json"),
                        "factor_snapshot": snapshot.model_dump(mode="json")},
            "bundle": {"stock": {"ticker": "AAPL", "company_name": "Apple", "exchange": "NASDAQ"},
                       "data_mode": "standard", "prices": prices, "weekly_history": [],
                       "quote": {**quote, "retrieved_at": "2026-06-19T20:00:30Z"}, "indicators": calculate_indicators("AAPL", prices),
                       "evidence": evidence, "macro_context": [
                           {"series": {**item, "frequency": "monthly"}, "observations": [
                               {**item, "series_code": item["code"]}]} for item in macro]}}


def test_valid_capture_and_mismatched_page_are_distinguished():
    payload = capture()
    result = verifier.audit_capture(payload)
    assert result["passed"], result
    payload["bundle"]["prices"][-1]["close"] = 100
    result = verifier.audit_capture(payload)
    assert not result["passed"]
    assert not result["checks"]["page_history"]


def test_missing_quote_stale_evidence_and_fixture_fail_closed():
    for mutate, check in [
        (lambda p: p["session"]["analysis_context"].update(market_quote=None), "quote_current"),
        (lambda p: p["bundle"].update(data_mode="review_fixture"), "aapl_standard"),
        (lambda p: p["session"]["analysis_context"]["evidence"][0].update(freshness={"status": "stale"}), "evidence_provenance"),
    ]:
        payload = deepcopy(capture())
        mutate(payload)
        result = verifier.audit_capture(payload)
        assert not result["passed"]
        assert not result["checks"][check]


def test_invalid_capture_never_echoes_input():
    result = verifier.audit_capture({"session": "private-secret"})
    assert result == {"passed": False, "checks": {"schema": False}}


def test_malformed_page_timestamp_and_duplicate_macro_codes_fail_safely():
    payload = capture()
    payload["bundle"]["quote"]["as_of"] = "private-invalid-time"
    result = verifier.audit_capture(payload)
    assert result["checks"]["page_quote"] is False
    assert "private-invalid-time" not in str(result)
    payload = capture()
    context = payload["session"]["analysis_context"]
    context["macro_context"] = [context["macro_context"][0]] * 7
    assert verifier.audit_capture(payload)["checks"]["macro_provenance"] is False


def test_capture_time_not_wall_clock_controls_completed_history_check():
    payload = capture()
    payload["session"]["analysis_context"]["captured_at"] = "2026-06-19T19:00:00Z"
    result = verifier.audit_capture(payload)
    assert result["checks"]["daily_history"] is False
    assert result["checks"]["quote_current"] is False


def test_future_evidence_and_missing_quote_retrieval_fail():
    payload = capture()
    payload["session"]["analysis_context"]["evidence"][0]["published_at"] = "2099-01-01"
    assert verifier.audit_capture(payload)["checks"]["evidence_provenance"] is False
    payload = capture()
    del payload["bundle"]["quote"]["retrieved_at"]
    assert verifier.audit_capture(payload)["checks"]["page_quote"] is False


def test_indicator_disagreement_is_detected():
    payload = capture()
    payload["bundle"]["indicators"]["rsi"] += 1
    assert verifier.audit_capture(payload)["checks"]["page_indicators"] is False


def test_cli_invalid_input_has_nonzero_exit_and_redacted_json(tmp_path):
    import json
    import os
    import subprocess
    import sys

    path = tmp_path / "capture.json"
    path.write_text('{"private-secret": invalid}')
    result = subprocess.run(
        [sys.executable, str(Path(verifier.__file__)), "--input", str(path)],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 1
    assert json.loads(result.stdout) == {"passed": False, "error": "invalid_capture"}
    assert result.stderr == ""
    assert "private-secret" not in result.stdout
