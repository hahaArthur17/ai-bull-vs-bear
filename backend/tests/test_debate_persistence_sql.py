from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260827_v2_debate_persistence.sql"
).read_text(encoding="utf-8")
RPC_MIGRATION_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260827_v2_debate_persistence_rpc.sql"
).read_text(encoding="utf-8")
INTERRUPTION_MIGRATION_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260909_debate_draft_interruption.sql"
).read_text(encoding="utf-8")
CONFLICT_MIGRATION_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260911_postgrest_conflict_status.sql"
).read_text(encoding="utf-8")
TRANSPORT_REPLAY_MIGRATION_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260911_provider_attempt_transport_replay.sql"
).read_text(encoding="utf-8")


DEBATE_TABLES = (
    "debate_sessions",
    "debate_messages",
    "debate_message_evidence",
    "debate_interventions",
    "debate_jobs",
)


def test_debate_migration_creates_all_canonical_tables_without_queue_transport() -> None:
    for table in DEBATE_TABLES:
        assert f"create table if not exists public.{table}" in MIGRATION_SQL

    assert "create extension" not in MIGRATION_SQL
    assert "pgmq" not in MIGRATION_SQL.lower()
    assert "credentials" in MIGRATION_SQL
    assert "queue transport remains a separate phase 5 migration" in MIGRATION_SQL.lower()


def test_debate_session_constraints_match_the_domain_state_contract() -> None:
    for status in (
        "created",
        "queued_round_1",
        "running_round_1",
        "awaiting_user",
        "queued_round_2",
        "running_round_2",
        "completed",
        "cancel_requested",
        "cancelled",
        "failed",
    ):
        assert f"'{status}'" in MIGRATION_SQL

    assert "debate_sessions_terminal_timestamp" in MIGRATION_SQL
    assert "debate_sessions_safe_error" in MIGRATION_SQL
    assert "debate_sessions_updated_after_created" in MIGRATION_SQL
    assert "jsonb_typeof(analysis_context) = 'object'" in MIGRATION_SQL
    assert "jsonb_typeof(factor_snapshot) = 'object'" in MIGRATION_SQL
    assert "char_length(initial_question) <= 500" in MIGRATION_SQL


def test_debate_message_and_intervention_constraints_enforce_ownership_and_shape() -> None:
    assert "debate_messages_session_branch_sequence_unique" in MIGRATION_SQL
    assert "debate_messages_role_kind" in MIGRATION_SQL
    assert "debate_messages_agent_round" in MIGRATION_SQL
    assert "debate_messages_completion" in MIGRATION_SQL
    assert "char_length(content) <= 6000" in MIGRATION_SQL
    assert "cardinality(terms) <= 12" in MIGRATION_SQL
    assert "debate_interventions_session_owner_fk" in MIGRATION_SQL
    assert "debate_interventions_selected_message_fk" in MIGRATION_SQL
    assert "char_length(selected_text) between 1 and 500" in MIGRATION_SQL
    assert "char_length(question) between 1 and 500" in MIGRATION_SQL


def test_debate_job_ledger_has_idempotency_worker_indexes_and_lifecycle_checks() -> None:
    assert "idempotency_key text not null unique" in MIGRATION_SQL
    assert "debate_jobs_attempt_limit" in MIGRATION_SQL
    assert "debate_jobs_token_sum" in MIGRATION_SQL
    assert "debate_jobs_running_state" in MIGRATION_SQL
    assert "debate_jobs_terminal_timestamp" in MIGRATION_SQL
    assert "debate_jobs_safe_error" in MIGRATION_SQL
    assert "debate_jobs_worker_claim_idx" in MIGRATION_SQL
    assert "debate_jobs_session_created_idx" in MIGRATION_SQL
    assert "debate_jobs_one_active_per_session_idx" in MIGRATION_SQL
    assert "where status in ('queued', 'running')" in MIGRATION_SQL


def test_debate_tables_are_owner_read_only_for_authenticated_clients() -> None:
    for table in DEBATE_TABLES:
        assert f"alter table public.{table} enable row level security" in MIGRATION_SQL

    authenticated_grant = MIGRATION_SQL.split("grant select on table", 1)[1].split(
        "to authenticated;", 1
    )[0]
    for table in DEBATE_TABLES:
        assert f"public.{table}" in authenticated_grant

    assert "revoke all on table" in MIGRATION_SQL
    assert "from anon, authenticated" in MIGRATION_SQL
    assert "grant all privileges on table" in MIGRATION_SQL
    assert "to service_role" in MIGRATION_SQL
    assert "auth.uid() = user_id" in MIGRATION_SQL
    assert "debate_sessions.user_id = auth.uid()" in MIGRATION_SQL
    assert "for insert" not in MIGRATION_SQL.lower()
    assert "for update" not in MIGRATION_SQL.lower()
    assert "for delete" not in MIGRATION_SQL.lower()


def test_debate_migration_has_owner_and_query_path_indexes() -> None:
    for index in (
        "debate_sessions_user_created_idx",
        "debate_sessions_status_updated_idx",
        "debate_messages_generation_idx",
        "debate_interventions_session_created_idx",
        "debate_jobs_worker_claim_idx",
        "debate_jobs_session_created_idx",
    ):
        assert f"create index if not exists {index}" in MIGRATION_SQL
    assert "create unique index if not exists debate_jobs_one_active_per_session_idx" in (
        MIGRATION_SQL
    )


def test_debate_transaction_rpcs_are_service_only_and_queue_independent() -> None:
    assert "function public.create_debate_session_with_job" in RPC_MIGRATION_SQL
    assert "function public.append_debate_message" in RPC_MIGRATION_SQL
    assert "jsonb_populate_record(null::public.debate_sessions" in RPC_MIGRATION_SQL
    assert "jsonb_populate_record(null::public.debate_jobs" in RPC_MIGRATION_SQL
    assert "jsonb_populate_record(null::public.debate_messages" in RPC_MIGRATION_SQL
    assert "jsonb_populate_recordset(" in RPC_MIGRATION_SQL
    assert "errcode = '23505'" in RPC_MIGRATION_SQL
    assert "for update" in RPC_MIGRATION_SQL.lower()
    assert "current_session.active_generation_id" in RPC_MIGRATION_SQL
    assert "current_session.status in ('cancel_requested', 'cancelled', 'completed', 'failed')" in (
        RPC_MIGRATION_SQL
    )
    assert "set search_path = ''" in RPC_MIGRATION_SQL
    assert "from public, anon, authenticated" in RPC_MIGRATION_SQL
    assert RPC_MIGRATION_SQL.count("to service_role;") == 2
    assert "security definer" not in RPC_MIGRATION_SQL.lower()
    assert "pgmq" not in RPC_MIGRATION_SQL.lower()


def test_debate_rpc_conflicts_map_to_http_409_without_serialization_retries() -> None:
    assert "'40001'" not in RPC_MIGRATION_SQL
    assert "'40001'" not in INTERRUPTION_MIGRATION_SQL
    assert "'PT409'" in RPC_MIGRATION_SQL
    assert "'PT409'" in INTERRUPTION_MIGRATION_SQL
    assert "pg_get_functiondef" in CONFLICT_MIGRATION_SQL
    assert "'PT409'" in CONFLICT_MIGRATION_SQL
    continue_definition = INTERRUPTION_MIGRATION_SQL.split(
        "create or replace function public.continue_interrupted_debate", 1
    )[1].split("revoke all on function public.continue_interrupted_debate", 1)[0]
    assert "security definer" in continue_definition.lower()
    assert "set search_path=''" in continue_definition.lower()


def test_provider_dispatch_transport_retry_requires_the_exact_timestamp() -> None:
    assert "existing.dispatched_at=dispatch_debate_provider_attempt.dispatched_at" in (
        INTERRUPTION_MIGRATION_SQL
    )
    assert "existing.outcome in ('dispatched','completed','failed')" in (
        TRANSPORT_REPLAY_MIGRATION_SQL
    )
    assert "from public,anon,authenticated" in TRANSPORT_REPLAY_MIGRATION_SQL
    assert "to service_role;" in TRANSPORT_REPLAY_MIGRATION_SQL
