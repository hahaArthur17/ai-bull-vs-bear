from app.services.guardrails import DISCLAIMER, apply_guardrails


def test_guardrails_rewrite_financial_advice() -> None:
    safe_text, status, rewritten = apply_guardrails("You should buy this stock. Guaranteed profit.")
    assert status == "rewritten"
    assert "buy" not in safe_text.lower()
    assert "guaranteed profit" in rewritten
    assert DISCLAIMER in safe_text

