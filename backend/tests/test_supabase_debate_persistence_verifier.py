from datetime import datetime, timezone
from uuid import UUID

import httpx

from scripts.verify_supabase_debate_persistence import (
    AuthSession,
    HostedDebatePersistenceVerifier,
)


USER_ID = UUID("00000000-0000-4000-8000-000000000501")
NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def test_verifier_fixture_follows_runtime_state_transitions() -> None:
    fixture = HostedDebatePersistenceVerifier._build_fixture(USER_ID, 1, NOW, "test")

    assert fixture.session.status == "created"
    assert fixture.queued_session.status == "queued_round_1"
    assert fixture.running_session.status == "running_round_1"
    assert fixture.job.status == "queued"
    assert fixture.running_job.status == "running"
    assert fixture.running_job.attempt_count == 1
    assert fixture.message.session_id == fixture.session.id
    assert fixture.citation.message_id == fixture.message.id
    assert fixture.intervention.selected_message_id == fixture.message.id


def test_authenticated_rpc_probe_uses_runtime_paths_and_user_token() -> None:
    seen_paths: list[str] = []

    def deny(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        assert request.headers["apikey"] == "anon-test"
        assert request.headers["authorization"] == "Bearer user-token"
        return httpx.Response(403)

    verifier = HostedDebatePersistenceVerifier(
        "https://example.supabase.co",
        "anon-test",
        "sb_secret_test",
        httpx.Client(transport=httpx.MockTransport(deny)),
    )
    fixture = verifier._build_fixture(USER_ID, 1, NOW, "test")

    assert verifier._authenticated_rpcs_rejected(
        AuthSession(USER_ID, "user-token"),
        fixture,
    )
    assert seen_paths == [
        "/rest/v1/rpc/create_debate_session_with_job",
        "/rest/v1/rpc/append_debate_message",
    ]
