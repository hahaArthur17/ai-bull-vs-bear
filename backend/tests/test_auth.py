import httpx
import pytest
from app.services.auth import SupabaseAuthVerifier, extract_bearer_token
from fastapi import HTTPException


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


@pytest.mark.parametrize("status_code", [429, 500, 502, 503])
def test_auth_outage_does_not_discard_a_valid_session(status_code: int) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status_code, text="private upstream detail")
        )
    )
    verifier = SupabaseAuthVerifier("https://example.supabase.co", "anon-key", client)

    with pytest.raises(HTTPException) as unavailable:
        verifier.verify("valid-token")

    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == "Authentication service unavailable"


@pytest.mark.parametrize("body", ["not-json", "[]", "null", '"user"'])
def test_malformed_auth_response_fails_safely(body: str) -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    )
    verifier = SupabaseAuthVerifier("https://example.supabase.co", "anon-key", client)

    with pytest.raises(HTTPException) as unavailable:
        verifier.verify("valid-token")

    assert unavailable.value.status_code == 503
    assert unavailable.value.detail == "Authentication service unavailable"
