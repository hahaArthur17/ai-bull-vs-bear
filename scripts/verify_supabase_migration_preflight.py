#!/usr/bin/env python3
"""Inspect hosted Supabase migration state without changing remote data."""

from __future__ import annotations

import json

import httpx

from app.config import get_settings
from app.services.supabase_headers import service_headers


CATALOG_MIGRATIONS = (
    "20260827_stock_catalog_coverage.sql",
    "20260827_stock_catalog_search.sql",
    "20260827_stock_catalog_seed.sql",
)
DEBATE_MIGRATIONS = (
    "20260827_v2_debate_persistence.sql",
    "20260827_v2_debate_persistence_rpc.sql",
)
QUEUE_MIGRATIONS = ("20260828_v2_debate_queue.sql",)

CATALOG_COLUMNS = (
    "coverage_status",
    "aliases",
    "country",
    "is_active",
    "sec_cik",
)
DEBATE_TABLE_PATHS = (
    "/debate_sessions",
    "/debate_messages",
    "/debate_message_evidence",
    "/debate_interventions",
    "/debate_jobs",
)
DEBATE_RPC_PATHS = (
    "/rpc/create_debate_session_with_job",
    "/rpc/append_debate_message_with_evidence",
)
QUEUE_RPC_PATHS = (
    "/rpc/enqueue_debate_session_job",
    "/rpc/enqueue_debate_round_two",
    "/rpc/claim_debate_job",
    "/rpc/archive_debate_job",
    "/rpc/retry_debate_job",
    "/rpc/requeue_debate_job",
    "/rpc/fail_exhausted_debate_job",
)


class HostedMigrationPreflight:
    def __init__(
        self,
        supabase_url: str,
        secret_key: str,
        client: httpx.Client | None = None,
    ) -> None:
        if not supabase_url.strip() or not secret_key.strip():
            raise ValueError("Supabase migration preflight requires a URL and secret key")
        self.openapi_url = f"{supabase_url.rstrip('/')}/rest/v1/"
        self.secret_key = secret_key
        self.client = client or httpx.Client(timeout=15.0)

    def inspect(self) -> dict[str, object]:
        headers = service_headers(self.secret_key, "return=minimal")
        headers["Accept"] = "application/openapi+json"
        try:
            response = self.client.get(self.openapi_url, headers=headers)
        except httpx.RequestError as exc:
            raise RuntimeError("Supabase migration preflight is unavailable") from exc
        if response.status_code != 200:
            raise RuntimeError(
                f"Supabase migration preflight failed with status {response.status_code}"
            )
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Supabase migration preflight returned an invalid schema")
        paths = payload.get("paths")
        definitions = payload.get("definitions")
        if not isinstance(paths, dict) or not isinstance(definitions, dict):
            raise RuntimeError("Supabase migration preflight returned an invalid schema")
        stock_definition = definitions.get("stocks")
        stock_properties = (
            stock_definition.get("properties", {})
            if isinstance(stock_definition, dict)
            else {}
        )
        if not isinstance(stock_properties, dict):
            stock_properties = {}

        catalog_columns = {
            column: column in stock_properties for column in CATALOG_COLUMNS
        }
        catalog_rpc = "/rpc/search_stock_catalog" in paths
        debate_tables = {path: path in paths for path in DEBATE_TABLE_PATHS}
        debate_rpcs = {path: path in paths for path in DEBATE_RPC_PATHS}
        queue_rpcs = {path: path in paths for path in QUEUE_RPC_PATHS}
        catalog_deployed = all(catalog_columns.values()) and catalog_rpc
        debate_deployed = all(debate_tables.values()) and all(debate_rpcs.values())
        queue_deployed = all(queue_rpcs.values())

        required_migrations: list[str] = []
        if not catalog_deployed:
            required_migrations.extend(CATALOG_MIGRATIONS)
        if not debate_deployed:
            required_migrations.extend(DEBATE_MIGRATIONS)
        if not queue_deployed:
            required_migrations.extend(QUEUE_MIGRATIONS)
        return {
            "postgrest_openapi_available": True,
            "catalog": {
                "deployed": catalog_deployed,
                "columns": catalog_columns,
                "search_rpc": catalog_rpc,
            },
            "debate_persistence": {
                "deployed": debate_deployed,
                "tables": debate_tables,
                "rpcs": debate_rpcs,
            },
            "queue": {
                "deployed": queue_deployed,
                "rpcs": queue_rpcs,
            },
            "required_migrations": required_migrations,
            "capacity_gate_required": not catalog_deployed,
        }


def main() -> None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise SystemExit("Missing SUPABASE_URL or SUPABASE_SECRET_KEY")
    report = HostedMigrationPreflight(
        settings.supabase_url,
        settings.supabase_secret_key,
    ).inspect()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
