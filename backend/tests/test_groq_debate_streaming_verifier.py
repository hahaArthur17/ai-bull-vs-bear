import asyncio

import pytest

from app.providers.streaming_debate import DeterministicStreamingDebateProvider
from scripts.verify_groq_debate_streaming import (
    LIVE_TURN_MAX_OUTPUT_CHARS,
    LIVE_TURN_MAX_COMPLETION_TOKENS,
    LIVE_TURN_REQUEST_BUDGET,
    LIVE_TRANSCRIPT_MAX_CHARS_PER_MESSAGE,
    QuotaBoundedStreamingProvider,
    diagnose_one_live_turn,
    parse_args,
    verify_one_live_round,
)


def test_live_verifier_proves_round_persistence_order_and_reconnect_without_network() -> None:
    report = asyncio.run(
        verify_one_live_round(
            DeterministicStreamingDebateProvider(max_chunk_characters=32),
            model_name="deterministic-test",
            expected_delta_source="deterministic",
            require_token_usage=False,
        )
    )

    assert all(report["checks"].values())
    assert report["live_turn_requests"] == LIVE_TURN_REQUEST_BUDGET
    assert report["completed_live_turn_requests"] == LIVE_TURN_REQUEST_BUDGET
    assert report["max_output_characters_per_turn"] == LIVE_TURN_MAX_OUTPUT_CHARS
    assert report["max_completion_tokens_per_turn"] == LIVE_TURN_MAX_COMPLETION_TOKENS
    assert (
        report["max_transcript_characters_per_message"]
        == LIVE_TRANSCRIPT_MAX_CHARS_PER_MESSAGE
    )
    assert report["canonical_messages"] == 7
    assert report["token_usage"]["total"] == 0


def test_quota_wrapper_rejects_an_expanded_request_or_output_budget() -> None:
    provider = DeterministicStreamingDebateProvider()

    with pytest.raises(ValueError, match="one Round 1"):
        QuotaBoundedStreamingProvider(provider, request_budget=7)
    with pytest.raises(ValueError, match="between 300 and 1000"):
        QuotaBoundedStreamingProvider(provider, max_output_chars=1001)


def test_one_turn_diagnostic_reports_completion_without_content() -> None:
    report = asyncio.run(
        diagnose_one_live_turn(
            DeterministicStreamingDebateProvider(max_chunk_characters=32)
        )
    )

    assert report["completed"]
    assert report["delta_count"] > 0
    assert report["delta_characters"] > 0
    assert "content" not in report


def test_live_quota_requires_an_explicit_command_flag() -> None:
    assert not parse_args([]).confirm_live_quota
    args = parse_args(["--confirm-live-quota", "--diagnose-one-turn"])
    assert args.confirm_live_quota
    assert args.diagnose_one_turn
