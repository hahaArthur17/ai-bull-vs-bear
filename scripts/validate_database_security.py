#!/usr/bin/env python3
"""Execute base-table allow/deny tests on an isolated PostgreSQL cluster.

The harness substitutes real[] storage for pgvector and omits its IVFFlat index.
This tests actual grants and RLS policies without requiring pgvector locally;
it does not certify vector search, hosted Supabase, or PostgREST behavior.
"""

import re
from pathlib import Path

from local_postgres import resolve_pg_bin, run_psql, temporary_postgres

ROOT = Path(__file__).resolve().parents[1]


def access_control_schema() -> str:
    schema = (ROOT / "backend/supabase/schema.sql").read_text()
    schema = schema.replace("create extension if not exists vector;", "")
    schema = re.sub(r"\bvector(?:\(\d+\))?", "real[]", schema)
    return re.sub(
        r"create index if not exists evidence_chunks_embedding_idx.*?;",
        "",
        schema,
        flags=re.DOTALL,
    )


def verify() -> None:
    pg_bin = resolve_pg_bin(None)
    with temporary_postgres(pg_bin) as (_, socket):
        run_psql(
            pg_bin,
            socket,
            sql="""
            create role anon nologin;
            create role authenticated nologin;
            create role service_role nologin bypassrls;
            create schema auth;
            grant usage on schema auth to anon, authenticated;
            create table auth.users (id uuid primary key);
            create function auth.uid() returns uuid language sql stable as
              'select nullif(current_setting(''request.jwt.claim.sub'', true), '''')::uuid';
            -- Reproduce hosted projects that grant API roles access by default.
            alter default privileges in schema public
              grant all on tables to anon, authenticated;
        """,
        )
        run_psql(pg_bin, socket, sql=access_control_schema())
        tests = ROOT / "backend/tests/sql/test_base_table_access.sql"
        run_psql(pg_bin, socket, file=tests)
        atomic_tests = ROOT / "backend/tests/sql/test_analysis_atomicity.sql"
        run_psql(pg_bin, socket, file=atomic_tests)
        # Existing installations must receive the same policy, and repeated
        # application must preserve both the permissions and their data.
        migration = next(
            (ROOT / "backend/supabase/migrations").glob("*_harden_base_table_access.sql")
        )
        for _ in range(2):
            run_psql(pg_bin, socket, file=migration)
            run_psql(
                pg_bin,
                socket,
                file=next(
                    (ROOT / "backend/supabase/migrations").glob("*_atomic_analysis_persistence.sql")
                ),
            )
        run_psql(pg_bin, socket, file=tests)
        run_psql(pg_bin, socket, file=atomic_tests)
    print(
        "Database security passed: fresh schema, repeated migrations, RLS, atomic rollback, citation links and idempotent retries."
    )


if __name__ == "__main__":
    verify()
