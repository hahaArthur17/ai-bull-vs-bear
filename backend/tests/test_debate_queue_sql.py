from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
QUEUE_SQL = (
    REPOSITORY_ROOT
    / "backend/supabase/migrations/20260828_v2_debate_queue.sql"
).read_text(encoding="utf-8")


def test_queue_migration_creates_one_durable_server_only_queue() -> None:
    assert "create extension if not exists pgmq" in QUEUE_SQL
    assert "pgmq.create('debate_jobs')" in QUEUE_SQL
    assert "pgmq.create_unlogged" not in QUEUE_SQL
    assert "alter table pgmq.q_debate_jobs enable row level security" in QUEUE_SQL
    assert "grant execute" in QUEUE_SQL
    assert "to service_role" in QUEUE_SQL
    assert "from public, anon, authenticated" in QUEUE_SQL
    assert "to anon" not in QUEUE_SQL
    assert "to authenticated" not in QUEUE_SQL


def test_queue_migration_has_atomic_admission_and_identifier_only_payload() -> None:
    assert "function public.enqueue_debate_session_job" in QUEUE_SQL
    assert "pg_advisory_xact_lock" in QUEUE_SQL
    assert "insert into public.debate_sessions" in QUEUE_SQL
    assert "insert into public.debate_jobs" in QUEUE_SQL
    assert "pgmq.send('debate_jobs', queue_payload, 0)" in QUEUE_SQL
    assert "Debate Queue payload must contain identifiers only" in QUEUE_SQL
    for key in (
        "schema_version",
        "job_id",
        "session_id",
        "job_type",
        "trace_id",
        "enqueued_at",
    ):
        assert f"'{key}'" in QUEUE_SQL


def test_queue_migration_wraps_visibility_redelivery_archive_and_retry() -> None:
    assert "function public.claim_debate_job" in QUEUE_SQL
    assert "pgmq.read('debate_jobs', visibility_timeout_seconds, 1)" in QUEUE_SQL
    assert "'read_count', claimed.read_ct" in QUEUE_SQL
    assert "'visibility_deadline', claimed.vt" in QUEUE_SQL
    assert "function public.archive_debate_job" in QUEUE_SQL
    assert "pgmq.archive('debate_jobs', queue_message_id)" in QUEUE_SQL
    assert "function public.retry_debate_job" in QUEUE_SQL
    assert "pgmq.set_vt('debate_jobs', queue_message_id, delay_seconds)" in QUEUE_SQL
    assert "function public.requeue_debate_job" in QUEUE_SQL
    assert "function public.fail_exhausted_debate_job" in QUEUE_SQL
    assert "status = 'queued'" in QUEUE_SQL
    assert "safe_error_code = 'debate_retry_exhausted'" in QUEUE_SQL
    assert QUEUE_SQL.count("security definer") == 6
    assert QUEUE_SQL.count("set search_path = ''") == 6
    assert QUEUE_SQL.count("to service_role;") == 6
