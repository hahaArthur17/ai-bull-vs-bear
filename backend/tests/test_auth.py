import httpx
import pytest
from fastapi import HTTPException

from app.services.auth import SupabaseAuthVerifier, extract_bearer_token


def test_extract_bearer_token_requires_valid_scheme() -> None:
    assert extract_bearer_token("Bearer session-token") == "session-token"
    with pytest.raises(HTTPException) as missing:
        extract_bearer_token(None)
    with pytest.raises(HTTPException) as malformed:
        extract_bearer_token("Basic session-token")
    assert missing.value.status_code == 401
    assert malformed.value.status_code == 401


def test_supabase_auth_verifier_returns_server_confirmed_user() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["apikey"] == "anon-key"
        assert request.headers["authorization"] == "Bearer valid-token"
        return httpx.Response(200, json={"id": "user-123"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    verifier = SupabaseAuthVerifier("https://example.supabase.co", "anon-key", client)

    context = verifier.verify("valid-token")

    assert context.user_id == "user-123"
    assert context.access_token == "valid-token"


def test_supabase_auth_verifier_rejects_invalid_token_without_leaking_details() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401)))
    verifier = SupabaseAuthVerifier("https://example.supabase.co", "anon-key", client)

    with pytest.raises(HTTPException) as invalid:
        verifier.verify("invalid-token")

    assert invalid.value.status_code == 401
    assert invalid.value.detail == "Invalid or expired access token"
