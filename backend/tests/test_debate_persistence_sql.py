from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260827_v2_debate_persistence.sql"
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
