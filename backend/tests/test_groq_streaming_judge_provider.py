from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.agents import DebateJudgeRequest
from app.domain.debate import DebateMessage
from app.providers.groq_streaming_judge import (
    GroqStreamingJudgeProvider,
    build_groq_judge_prompt,
)
from app.services.debate_streaming import DebateTurnStreamError, collect_debate_judge_stream
from test_groq_streaming_debate_provider import FakeGroqClient, FakeUsage, chunk, grounded_request


def judge_request(*, max_output_chars: int = 800) -> DebateJudgeRequest:
    turn = grounded_request(max_output_chars=max_output_chars)
    return DebateJudgeRequest(
        session_id=turn.session_id,
        branch_id=turn.branch_id,
        phase="interim",
        analysis_context=turn.analysis_context,
        factor_snapshot=turn.factor_snapshot,
        transcript=(
            DebateMessage(
                id=UUID("00000000-0000-4000-8000-000000000504"),
                session_id=turn.session_id,
                branch_id=turn.branch_id,
                generation_id=turn.generation_id,
                sequence_number=1,
                round_number=1,
                exchange_number=1,
                role="bull",
                message_kind="argument",
                content="The constructive case depends on the supplied evidence.",
                created_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
            ),
        ),
        allowed_evidence_ids=turn.allowed_evidence_ids,
        max_output_chars=max_output_chars,
    )


def collect(provider: GroqStreamingJudgeProvider, request: DebateJudgeRequest | None = None):
    return asyncio.run(collect_debate_judge_stream(provider, request or judge_request()))


def test_live_judge_streams_summary_and_reports_usage() -> None:
    client = FakeGroqClient(
        [
            chunk("The cases share uncertainty [E1], but weigh momentum differently."),
            chunk(finish_reason="stop", usage=FakeUsage(23, 11)),
        ]
    )
    provider = GroqStreamingJudgeProvider(
        api_key="test-key",
        model="openai/gpt-oss-20b",
        client=client,
    )

    result = collect(provider, judge_request(max_output_chars=1200))

    assert result.draft.evidence_ids == ("news-1",)
    assert result.usage.prompt_tokens == 23
    assert result.usage.completion_tokens == 11
    assert result.usage.total_tokens == 34
    assert result.delta_count >= 1
    assert client.completions.kwargs is not None
    assert client.completions.kwargs["stream"] is True
    assert client.completions.kwargs["max_completion_tokens"] == 800


def test_judge_prompt_uses_a_bounded_projection_and_repeats_citation_contract() -> None:
    base = judge_request(max_output_chars=2400)
    transcript = tuple(
        base.transcript[0].model_copy(
            update={
                "sequence_number": index,
                "content": "A" * 4000,
            }
        )
        for index in range(1, 15)
    )
    request = base.model_copy(
        update={
            "transcript": transcript,
            "factor_snapshot": base.factor_snapshot.model_copy(
                update={"observations": base.factor_snapshot.observations * 51}
            ),
        }
    )

    prompt = build_groq_judge_prompt(request)

    assert len(prompt) < 16_000
    assert prompt.count("A" * 600) == 12
    assert prompt.index("<response_contract>") > prompt.index("</frozen_context>")
    assert "begin the response with one or more relevant exact evidence aliases" in prompt


@pytest.mark.parametrize(
    "summary",
    ["The cases cite invented evidence [E9].", "The evidence is material but uncited."],
)
def test_live_judge_rejects_invalid_or_missing_citations(summary: str) -> None:
    provider = GroqStreamingJudgeProvider(
        api_key="test-key",
        model="openai/gpt-oss-20b",
        client=FakeGroqClient([chunk(summary), chunk(finish_reason="stop")]),
    )

    with pytest.raises(DebateTurnStreamError, match="Judge provider stream failed"):
        collect(provider)


def test_live_judge_rejects_output_over_request_bound() -> None:
    request = judge_request(max_output_chars=300)
    provider = GroqStreamingJudgeProvider(
        api_key="test-key",
        model="openai/gpt-oss-20b",
        client=FakeGroqClient([chunk("x" * 301), chunk(finish_reason="stop")]),
    )

    with pytest.raises(DebateTurnStreamError, match="Judge provider stream failed"):
        collect(provider, request)


def test_judge_completion_cap_is_forwarded_and_default_is_independent():
    from app.config import Settings
    from app.providers.debate_factory import build_debate_streaming_judge_provider
    client = FakeGroqClient([chunk("Uncertain evidence [E1]."), chunk(finish_reason="stop")])
    provider = GroqStreamingJudgeProvider(api_key="test-key", model="test-model", max_completion_tokens=200, client=client)
    collect(provider)
    assert client.completions.kwargs["max_completion_tokens"] == 200
    settings = Settings(_env_file=None, debate_streaming_provider="groq")
    assert build_debate_streaming_judge_provider(settings).name != "groq-live-judge"
