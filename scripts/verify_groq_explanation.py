#!/usr/bin/env python3
"""Run one explicitly authorized, quota-bounded live Groq term explanation."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.config import get_settings
from app.domain.debate import DebateMessage
from app.domain.explanations import ExplanationAgentRequest
from app.domain.factors import FactorSnapshot
from app.providers.groq_explanation import GroqExplanationProvider
from app.services.analysis_context import build_analysis_context


LIVE_EXPLANATION_REQUEST_BUDGET = 1
LIVE_EXPLANATION_MAX_COMPLETION_TOKENS = 160
LIVE_EXPLANATION_MAX_OUTPUT_CHARS = 1600


def build_controlled_request() -> ExplanationAgentRequest:
    """Return synthetic, bounded input that contains no user or market-data record."""

    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    session_id = uuid5(NAMESPACE_URL, "ai-bull-vs-bear:groq-explanation-smoke")
    branch_id = uuid5(session_id, "branch")
    context = build_analysis_context(
        "AAPL",
        as_of=as_of,
        evidence=[
            {
                "id": "groq-explanation-smoke-evidence",
                "ticker": "AAPL",
                "source_type": "filing",
                "title": "Controlled dated filing context",
                "published_at": as_of,
                "excerpt": (
                    "This synthetic smoke-test filing describes a dated company context and "
                    "does not predict a future return."
                ),
                "metadata": {"fixture": "quota_bounded_live_groq_explanation"},
            }
        ],
    )
    source = DebateMessage(
        id=uuid5(session_id, "source-message"),
        session_id=session_id,
        branch_id=branch_id,
        generation_id=uuid5(session_id, "generation"),
        sequence_number=1,
        round_number=1,
        exchange_number=1,
        role="bull",
        message_kind="argument",
        content=(
            "The moving average smooths recent price observations, so it offers only bounded "
            "trend context for this argument."
        ),
        is_complete=True,
        created_at=as_of,
    )
    return ExplanationAgentRequest(
        session_id=session_id,
        branch_id=branch_id,
        ticker="AAPL",
        source_message=source,
        selected_text="moving average",
        question="What does this term mean in the argument?",
        analysis_context=context,
        factor_snapshot=FactorSnapshot(ticker="AAPL", as_of=as_of),
        allowed_evidence_ids=frozenset({"groq-explanation-smoke-evidence"}),
    )


def verify_one_live_explanation(provider: Any) -> dict[str, Any]:
    """Make exactly one bounded request and return diagnostics without its text."""

    request = build_controlled_request()
    draft = provider.generate_explanation(request)
    checks = {
        "one_request_budget": LIVE_EXPLANATION_REQUEST_BUDGET == 1,
        "nonempty_content": bool(draft.content.strip()),
        "output_bounded": len(draft.content) <= LIVE_EXPLANATION_MAX_OUTPUT_CHARS,
        "only_linked_evidence": set(draft.evidence_ids) <= request.allowed_evidence_ids,
        "selected_term_preserved": request.selected_text in draft.terms,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Live Groq Explanation smoke failed checks: {checks}")
    return {
        "checks": checks,
        "model": provider.model,
        "provider": provider.name,
        "live_explanation_requests": LIVE_EXPLANATION_REQUEST_BUDGET,
        "max_completion_tokens": LIVE_EXPLANATION_MAX_COMPLETION_TOKENS,
        "max_output_characters": LIVE_EXPLANATION_MAX_OUTPUT_CHARS,
        "content_characters": len(draft.content),
        "citation_count": len(draft.evidence_ids),
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-live-quota",
        action="store_true",
        help="Acknowledge that this command makes exactly one live Groq request.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if not args.confirm_live_quota:
        raise SystemExit(
            "Refusing live Groq requests without --confirm-live-quota (one request)."
        )
    settings = get_settings()
    if settings.explanation_provider.strip().lower() != "groq":
        raise SystemExit("Set EXPLANATION_PROVIDER=groq for this explicit smoke run.")
    if not settings.groq_api_key:
        raise SystemExit("GROQ_API_KEY is required for the live Explanation smoke run.")
    provider = GroqExplanationProvider(
        api_key=settings.groq_api_key,
        model=settings.explanation_groq_model,
        timeout_seconds=settings.explanation_provider_timeout_seconds,
        max_completion_tokens=LIVE_EXPLANATION_MAX_COMPLETION_TOKENS,
    )
    try:
        report = verify_one_live_explanation(provider)
    finally:
        provider.close()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
