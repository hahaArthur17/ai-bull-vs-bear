from __future__ import annotations

import httpx
import pytest

from scripts.verify_supabase_migration_preflight import (
    CATALOG_MIGRATIONS,
    DEBATE_MIGRATIONS,
    QUEUE_MIGRATIONS,
    HostedMigrationPreflight,
)


def build_preflight(
    handler: httpx.MockTransport,
    *,
    secret_key: str = "sb_secret_preflight",
) -> HostedMigrationPreflight:
    return HostedMigrationPreflight(
        "https://example.supabase.co",
        secret_key,
        httpx.Client(transport=handler),
    )


def test_preflight_reports_only_missing_migration_groups() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.headers["apikey"] == "sb_secret_preflight"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={
                "definitions": {
                    "stocks": {
                        "properties": {
                            "coverage_status": {},
                            "aliases": {},
                            "country": {},
                            "is_active": {},
                            "sec_cik": {},
                        }
                    }
                },
                "paths": {"/rpc/search_stock_catalog": {}},
            },
        )

    report = build_preflight(httpx.MockTransport(respond)).inspect()

    assert report["catalog"]["deployed"] is True  # type: ignore[index]
    assert report["debate_persistence"]["deployed"] is False  # type: ignore[index]
    assert report["queue"]["deployed"] is False  # type: ignore[index]
    assert report["required_migrations"] == [*DEBATE_MIGRATIONS, *QUEUE_MIGRATIONS]
    assert report["capacity_gate_required"] is False


def test_preflight_matches_runtime_debate_rpc_paths() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "definitions": {
                    "stocks": {"properties": {}},
                    "debate_sessions": {},
                    "debate_messages": {},
                    "debate_message_evidence": {},
                    "debate_interventions": {},
                    "debate_jobs": {},
                },
                "paths": {
                    "/debate_sessions": {},
                    "/debate_messages": {},
                    "/debate_message_evidence": {},
                    "/debate_interventions": {},
                    "/debate_jobs": {},
                    "/rpc/create_debate_session_with_job": {},
                    "/rpc/append_debate_message": {},
                },
            },
        )

    report = build_preflight(httpx.MockTransport(respond)).inspect()

    assert report["debate_persistence"]["deployed"] is True  # type: ignore[index]
    assert report["debate_persistence"]["rpcs"] == {  # type: ignore[index]
        "/rpc/create_debate_session_with_job": True,
        "/rpc/append_debate_message": True,
    }


def test_preflight_is_read_only_and_does_not_leak_remote_error_body() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(500, json={"secret": "must-not-leak"})

    preflight = build_preflight(httpx.MockTransport(fail))

    with pytest.raises(RuntimeError, match="status 500") as error:
        preflight.inspect()

    assert "must-not-leak" not in str(error.value)
    assert [*CATALOG_MIGRATIONS, *DEBATE_MIGRATIONS, *QUEUE_MIGRATIONS] == [
        "20260827_stock_catalog_coverage.sql",
        "20260827_stock_catalog_search.sql",
        "20260827_stock_catalog_seed.sql",
        "20260827_v2_debate_persistence.sql",
        "20260827_v2_debate_persistence_rpc.sql",
        "20260828_v2_debate_queue.sql",
    ]
