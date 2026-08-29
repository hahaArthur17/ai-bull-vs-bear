#!/usr/bin/env python3
"""Run one explicitly authorized, quota-bounded live Groq Debate round."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timezone
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.config import get_settings
from app.domain.agents import DebateTurnRequest, DebateTurnStreamEvent
from app.domain.factors import (
    AnalysisContext,
    FactorFreshness,
    FactorObservation,
    FactorSnapshot,
)
from app.providers.debate_agents import DebateStreamingTurnProvider
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.providers.groq_streaming_debate import (
    GroqDebateStreamError,
    GroqStreamingDebateProvider,
)
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.debate_event_broker import InMemoryDebateEventBroker
from app.services.debate_preview import DebatePreviewService
from app.services.debate_worker import DebateWorker


LIVE_TURN_REQUEST_BUDGET = 6
LIVE_TURN_MAX_OUTPUT_CHARS = 1000
LIVE_TURN_MAX_COMPLETION_TOKENS = 220
LIVE_TRANSCRIPT_MAX_CHARS_PER_MESSAGE = 300
LIVE_POINT_MAX_CHARS = 160


class QuotaBoundedStreamingProvider:
    """Cap one Round 1 provider to six short, non-retried Turn requests."""

    def __init__(
        self,
        provider: DebateStreamingTurnProvider,
        *,
        request_budget: int = LIVE_TURN_REQUEST_BUDGET,
        max_output_chars: int = LIVE_TURN_MAX_OUTPUT_CHARS,
    ) -> None:
        if request_budget != LIVE_TURN_REQUEST_BUDGET:
            raise ValueError("The live smoke request budget must equal one Round 1")
        if not 300 <= max_output_chars <= LIVE_TURN_MAX_OUTPUT_CHARS:
            raise ValueError("The live smoke output bound must be between 300 and 1000")
        self.provider = provider
        self.request_budget = request_budget
        self.max_output_chars = max_output_chars
        self.request_count = 0
        self.name = provider.name
        self.version = f"{provider.version}-quota-smoke"
        self.completed_request_count = 0
        self.safe_failures: list[dict[str, Any]] = []

    async def stream_turn(
        self,
        request: DebateTurnRequest,
    ) -> AsyncIterator[DebateTurnStreamEvent]:
        if self.request_count >= self.request_budget:
            raise RuntimeError("Live Groq smoke exceeded its six-request budget")
        self.request_count += 1
        bounded_request = request.model_copy(
            update={
                "max_output_chars": self.max_output_chars,
                "transcript": tuple(
                    message.model_copy(
                        update={
                            "content": message.content[
                                :LIVE_TRANSCRIPT_MAX_CHARS_PER_MESSAGE
                            ]
                        }
                    )
                    for message in request.transcript
                ),
                "previously_used_points": tuple(
                    point[:LIVE_POINT_MAX_CHARS]
                    for point in request.previously_used_points
                ),
            }
        )
        try:
            async for event in self.provider.stream_turn(bounded_request):
                yield event
        except GroqDebateStreamError as exc:
            self.safe_failures.append(
                {
                    "type": type(exc).__name__,
                    "safe_message": str(exc),
                    "retryable": exc.retryable,
                }
            )
            raise
        self.completed_request_count += 1


def build_controlled_snapshot() -> tuple[AnalysisContext, FactorSnapshot]:
    """Return small, explicitly synthetic inputs for transport verification."""

    as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    evidence = (
        {
            "id": "groq-smoke-supportive",
            "ticker": "AAPL",
            "source_type": "filing",
            "title": "Controlled supportive filing excerpt",
            "published_at": as_of,
            "excerpt": (
                "In this synthetic smoke-test snapshot, revenue improved while "
                "management described continued product demand."
            ),
            "freshness": FactorFreshness(
                status="current",
                age_days=0,
                max_age_days=30,
                evaluated_at=as_of,
            ),
            "metadata": {"fixture": "live_stream_transport_only"},
        },
        {
            "id": "groq-smoke-cautionary",
            "ticker": "AAPL",
            "source_type": "filing",
            "title": "Controlled cautionary filing excerpt",
            "published_at": as_of,
            "excerpt": (
                "In this synthetic smoke-test snapshot, management identified "
                "demand variability and currency movements as uncertainties."
            ),
            "freshness": FactorFreshness(
                status="current",
                age_days=0,
                max_age_days=30,
                evaluated_at=as_of,
            ),
            "metadata": {"fixture": "live_stream_transport_only"},
        },
    )
    context = AnalysisContext.model_validate(
        {
            "ticker": "AAPL",
            "as_of": as_of,
            "evidence": evidence,
            "allowed_evidence_ids": [item["id"] for item in evidence],
            "metadata": {"fixture": "quota_bounded_live_groq"},
        }
    )
    observations = (
        FactorObservation(
            id="groq-smoke-momentum",
            ticker="AAPL",
            factor_key="technical.momentum",
            category="technical",
            provider="controlled-smoke",
            label="Controlled momentum",
            as_of=as_of,
            value=1.0,
            unit="index",
            interpretation=(
                "The synthetic momentum input is supportive but cannot predict a return."
            ),
            direction="supportive",
            confidence="medium",
            provider_version="v1",
        ),
        FactorObservation(
            id="groq-smoke-valuation",
            ticker="AAPL",
            factor_key="fundamental.valuation",
            category="fundamental",
            provider="controlled-smoke",
            label="Controlled valuation uncertainty",
            as_of=as_of,
            value=1.0,
            unit="index",
            interpretation=(
                "The synthetic valuation input is cautionary and remains incomplete."
            ),
            direction="cautionary",
            confidence="medium",
            provider_version="v1",
        ),
    )
    return context, FactorSnapshot(
        ticker="AAPL",
        as_of=as_of,
        observations=observations,
    )


async def diagnose_one_live_turn(
    provider: DebateStreamingTurnProvider,
) -> dict[str, Any]:
    """Make one request and expose only bounded, non-sensitive diagnostics."""

    context, snapshot = build_controlled_snapshot()
    session_id = uuid5(NAMESPACE_URL, "ai-bull-vs-bear:groq-diagnostic-session")
    request = DebateTurnRequest(
        session_id=session_id,
        branch_id=uuid5(session_id, "branch"),
        generation_id=uuid5(session_id, "generation"),
        ticker="AAPL",
        role="bull",
        round_number=1,
        exchange_number=1,
        initial_question="How can the bounded snapshot support a Bull interpretation?",
        analysis_context=context,
        factor_snapshot=snapshot,
        allowed_evidence_ids=context.allowed_evidence_ids,
        max_output_chars=LIVE_TURN_MAX_OUTPUT_CHARS,
    )
    delta_count = 0
    delta_characters = 0
    completion = None
    try:
        async for event in provider.stream_turn(request):
            if event.kind == "delta":
                delta_count += 1
                delta_characters += len(event.delta)
            else:
                completion = event
    except Exception as exc:
        error_chain: list[dict[str, Any]] = []
        current: BaseException | None = exc
        while current is not None and len(error_chain) < 5:
            item: dict[str, Any] = {"type": type(current).__name__}
            status_code = getattr(current, "status_code", None)
            if isinstance(status_code, int):
                item["status_code"] = status_code
            if isinstance(current, GroqDebateStreamError):
                item["safe_message"] = str(current)
                item["retryable"] = current.retryable
            error_chain.append(item)
            current = current.__cause__
        return {
            "completed": False,
            "delta_count": delta_count,
            "delta_characters": delta_characters,
            "error_chain": error_chain,
        }

    return {
        "completed": completion is not None,
        "delta_count": delta_count,
        "delta_characters": delta_characters,
        "finish_reason": completion.finish_reason if completion is not None else None,
        "token_usage": (
            completion.usage.model_dump(mode="json") if completion is not None else None
        ),
    }


async def verify_one_live_round(
    provider: DebateStreamingTurnProvider,
    *,
    model_name: str,
    expected_delta_source: str,
    require_token_usage: bool,
) -> dict[str, Any]:
    """Exercise Queue, Worker, stream, persistence, and replay for Round 1."""

    bounded_provider = QuotaBoundedStreamingProvider(provider)
    repository = InMemoryDebateRepository()
    broker = InMemoryDebateEventBroker(max_events_per_session=4096)
    judge = DeterministicDebateProvider()
    service = DebatePreviewService(
        repository,
        judge,
        judge,
        streaming_turn_provider=bounded_provider,
        event_publisher=broker,
    )
    context, snapshot = build_controlled_snapshot()
    user_id = uuid5(NAMESPACE_URL, "ai-bull-vs-bear:groq-live-smoke")
    queued, admitted_job = service.create_queued_round_one(
        user_id=user_id,
        stock_id=1,
        ticker="AAPL",
        opening_side="bull",
        question="How can the same bounded snapshot support competing views?",
        idempotency_key=f"groq-live-smoke-{context.as_of}",
        analysis_context=context,
        factor_snapshot=snapshot,
    )
    worker = DebateWorker(
        repository,
        repository,
        service.orchestrator,
        visibility_timeout_seconds=30,
    )
    result = await worker.run_once()
    idle = await worker.run_once()

    session = repository.get_session(queued.id, user_id)
    job = repository.get_job(admitted_job.id)
    messages = repository.list_messages(
        queued.id,
        user_id,
        branch_id=queued.active_branch_id,
    )
    events = broker.replay(queued.id)
    live_messages = [message for message in messages if message.role in {"bull", "bear"}]
    citations = [
        citation
        for message in live_messages
        for citation in repository.list_message_evidence(message.id, user_id)
    ]
    delta_events = [event for event in events if event.type == "turn.delta"]
    completed_events = [event for event in events if event.type == "turn.completed"]
    delta_message_ids = {event.payload["message_id"] for event in delta_events}
    completed_message_ids = {
        event.payload["message"]["id"] for event in completed_events
    }
    replay_cursor = events[len(events) // 2].sequence
    resumed_events = broker.replay(queued.id, after_sequence=replay_cursor)
    canonical_reload = repository.get_session(queued.id, user_id)
    canonical_messages = repository.list_messages(
        queued.id,
        user_id,
        branch_id=queued.active_branch_id,
    )

    checks = {
        "worker_completed_and_queue_idle": (
            result.outcome == "completed" and idle.outcome == "idle"
        ),
        "round_one_persisted": (
            session is not None
            and session.status == "awaiting_user"
            and job is not None
            and job.status == "completed"
            and len(messages) == 7
            and len(live_messages) == LIVE_TURN_REQUEST_BUDGET
            and all(message.is_complete for message in messages)
        ),
        "live_request_budget_respected": (
            bounded_provider.request_count == LIVE_TURN_REQUEST_BUDGET
            and job is not None
            and job.provider_request_count == LIVE_TURN_REQUEST_BUDGET + 1
        ),
        "live_messages_grounded": (
            len(citations) >= LIVE_TURN_REQUEST_BUDGET
            and all(
                citation.evidence_id in context.allowed_evidence_ids
                for citation in citations
            )
        ),
        "ordered_live_deltas_completed": (
            [event.sequence for event in events]
            == list(range(1, len(events) + 1))
            and len(completed_events) == LIVE_TURN_REQUEST_BUDGET
            and completed_message_ids <= delta_message_ids
            and all(
                event.payload["source"] == expected_delta_source
                for event in delta_events
            )
        ),
        "canonical_reconnect_safe": (
            bool(resumed_events)
            and resumed_events[0].sequence == replay_cursor + 1
            and resumed_events[-1].type == "session.awaiting_user"
            and canonical_reload == session
            and canonical_messages == messages
        ),
        "token_usage_recorded": (
            job is not None
            and (
                job.prompt_tokens > 0
                and job.completion_tokens > 0
                and job.total_tokens == job.prompt_tokens + job.completion_tokens
                if require_token_usage
                else job.total_tokens == 0
            )
        ),
    }
    if not all(checks.values()):
        safe_diagnostics = {
            "worker_outcome": result.outcome,
            "second_worker_outcome": idle.outcome,
            "requests_started": bounded_provider.request_count,
            "requests_completed": bounded_provider.completed_request_count,
            "safe_provider_failures": bounded_provider.safe_failures,
            "session_status": session.status if session is not None else None,
            "job_status": job.status if job is not None else None,
            "job_safe_error_code": job.safe_error_code if job is not None else None,
            "canonical_messages": len(messages),
            "delta_events": len(delta_events),
            "completed_events": len(completed_events),
        }
        raise RuntimeError(
            "Live Groq Debate verification failed safely: "
            f"checks={checks}; diagnostics={safe_diagnostics}"
        )

    assert job is not None
    return {
        "checks": checks,
        "model": model_name,
        "live_turn_requests": bounded_provider.request_count,
        "completed_live_turn_requests": bounded_provider.completed_request_count,
        "max_output_characters_per_turn": bounded_provider.max_output_chars,
        "max_completion_tokens_per_turn": LIVE_TURN_MAX_COMPLETION_TOKENS,
        "max_transcript_characters_per_message": (
            LIVE_TRANSCRIPT_MAX_CHARS_PER_MESSAGE
        ),
        "canonical_messages": len(messages),
        "stream_events": len(events),
        "delta_events": len(delta_events),
        "citation_links": len(citations),
        "token_usage": {
            "prompt": job.prompt_tokens,
            "completion": job.completion_tokens,
            "total": job.total_tokens,
        },
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-live-quota",
        action="store_true",
        help="Acknowledge that this command makes at most six live Groq requests.",
    )
    parser.add_argument(
        "--diagnose-one-turn",
        action="store_true",
        help="Make one non-persisted Turn request and print only safe diagnostics.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    if not args.confirm_live_quota:
        raise SystemExit(
            "Refusing live Groq requests without --confirm-live-quota (six requests)."
        )
    settings = get_settings()
    if settings.debate_streaming_provider.strip().lower() != "groq":
        raise SystemExit("Set DEBATE_STREAMING_PROVIDER=groq for this explicit smoke run.")
    if not settings.groq_api_key:
        raise SystemExit("GROQ_API_KEY is required for the live Debate smoke run.")

    provider = GroqStreamingDebateProvider(
        api_key=settings.groq_api_key,
        model=settings.debate_groq_model,
        timeout_seconds=settings.debate_provider_timeout_seconds,
        max_completion_tokens=LIVE_TURN_MAX_COMPLETION_TOKENS,
    )
    if args.diagnose_one_turn:
        print(
            json.dumps(
                asyncio.run(diagnose_one_live_turn(provider)),
                indent=2,
                sort_keys=True,
            )
        )
        return
    report = asyncio.run(
        verify_one_live_round(
            provider,
            model_name=settings.debate_groq_model,
            expected_delta_source="live_provider",
            require_token_usage=True,
        )
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
