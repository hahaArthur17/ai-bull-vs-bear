from app.services.supabase_headers import service_headers


def test_service_headers_omit_bearer_for_current_secret_key() -> None:
    headers = service_headers("sb_secret_example", "return=minimal")

    assert headers == {
        "apikey": "sb_secret_example",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def test_service_headers_keep_bearer_for_legacy_service_role_jwt() -> None:
    headers = service_headers("legacy-jwt", "return=representation")

    assert headers["apikey"] == "legacy-jwt"
    assert headers["Authorization"] == "Bearer legacy-jwt"
