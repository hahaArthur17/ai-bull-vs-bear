import pytest

from app.providers.groq_explanation import GroqExplanationProvider
from scripts.verify_groq_explanation import (
    LIVE_EXPLANATION_MAX_COMPLETION_TOKENS,
    LIVE_EXPLANATION_MAX_OUTPUT_CHARS,
    LIVE_EXPLANATION_REQUEST_BUDGET,
    parse_args,
    verify_one_live_explanation,
)


class FakeCompletions:
    def create(self, **_kwargs):
        class Message:
            content = "A moving average smooths observed prices; the filing is limited context [E1]."

        class Choice:
            message = Message()

        class Response:
            choices = [Choice()]

        return Response()


class FakeClient:
    class Chat:
        completions = FakeCompletions()

    chat = Chat()


def test_live_explanation_verifier_reports_one_bounded_request_without_network() -> None:
    provider = GroqExplanationProvider(api_key="test-key", client=FakeClient())

    report = verify_one_live_explanation(provider)

    assert all(report["checks"].values())
    assert report["live_explanation_requests"] == LIVE_EXPLANATION_REQUEST_BUDGET
    assert report["max_completion_tokens"] == LIVE_EXPLANATION_MAX_COMPLETION_TOKENS
    assert report["max_output_characters"] == LIVE_EXPLANATION_MAX_OUTPUT_CHARS
    assert "content" not in report


def test_live_explanation_verifier_requires_an_explicit_command_flag() -> None:
    assert not parse_args([]).confirm_live_quota
    assert parse_args(["--confirm-live-quota"]).confirm_live_quota


def test_live_explanation_verifier_refuses_a_bad_provider_output() -> None:
    class BadClient:
        class Chat:
            class Completions:
                def create(self, **_kwargs):
                    class Message:
                        content = "A bad citation [E9]."

                    class Choice:
                        message = Message()

                    class Response:
                        choices = [Choice()]

                    return Response()

            completions = Completions()

        chat = Chat()

    provider = GroqExplanationProvider(api_key="test-key", client=BadClient())
    with pytest.raises(RuntimeError, match="invalid evidence citation"):
        verify_one_live_explanation(provider)
