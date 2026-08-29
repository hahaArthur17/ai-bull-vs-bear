from uuid import UUID

import httpx

from scripts.verify_supabase_debate_persistence import AuthSession
from scripts.verify_supabase_debate_queue import HostedDebateQueueVerifier
from scripts.verify_supabase_migration_preflight import QUEUE_RPC_PATHS


USER_ID = UUID("00000000-0000-4000-8000-000000000601")


def test_queue_verifier_covers_every_preflight_rpc_path() -> None:
    assert tuple(f"/{path}" for path in HostedDebateQueueVerifier.QUEUE_RPC_PAYLOADS) == (
        QUEUE_RPC_PATHS
    )


def test_authenticated_queue_probe_uses_user_token_and_is_denied() -> None:
    seen_paths: list[str] = []

    def deny(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        assert request.headers["apikey"] == "anon-test"
        assert request.headers["authorization"] == "Bearer user-token"
        return httpx.Response(403)

    transport = httpx.MockTransport(deny)
    verifier = HostedDebateQueueVerifier(
        "https://example.supabase.co",
        "anon-test",
        "sb_secret_test",
        client_factory=lambda: httpx.Client(transport=transport),
    )
    try:
        assert verifier._authenticated_queue_rpcs_rejected(
            AuthSession(USER_ID, "user-token")
        )
    finally:
        for client in verifier.clients:
            client.close()

    assert seen_paths == [
        f"/rest/v1/{path}" for path in HostedDebateQueueVerifier.QUEUE_RPC_PAYLOADS
    ]
