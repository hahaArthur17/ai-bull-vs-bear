-- Phase 5 durable Debate stage transport.
-- Apply only after the Phase 3 Debate persistence migrations. The mobile and
-- authenticated roles never receive direct Queue access.

create extension if not exists pgmq;

do $$
begin
  if not exists (
    select 1
    from pgmq.list_queues()
    where queue_name = 'debate_jobs'
  ) then
    perform pgmq.create('debate_jobs');
  end if;
end;
$$;

alter table pgmq.q_debate_jobs enable row level security;

create or replace function public.enqueue_debate_session_job(
  session_payload jsonb,
  job_payload jsonb,
  queue_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  requested_session_id uuid := (session_payload ->> 'id')::uuid;
  requested_job_id uuid := (job_payload ->> 'id')::uuid;
  queue_keys text[];
  stored_session jsonb;
  stored_job jsonb;
  sent_queue_message_id bigint;
begin
  select array_agg(key_name order by key_name)
  into queue_keys
  from jsonb_object_keys(queue_payload) as key_name;

  if queue_keys <> array[
    'enqueued_at',
    'job_id',
    'job_type',
    'schema_version',
    'session_id',
    'trace_id'
  ]::text[] then
    raise exception using
      errcode = '22023',
      message = 'Debate Queue payload must contain identifiers only';
  end if;
  if (queue_payload ->> 'schema_version')::integer <> 1
     or (queue_payload ->> 'job_id')::uuid <> requested_job_id
     or (queue_payload ->> 'session_id')::uuid <> requested_session_id
     or queue_payload ->> 'job_type' <> job_payload ->> 'job_type'
     or queue_payload ->> 'trace_id' !~ '^[A-Za-z0-9_-]{8,80}$'
     or job_payload ->> 'status' <> 'queued'
     or job_payload -> 'queue_message_id' is distinct from 'null'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'Debate Queue admission payloads do not match';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(requested_job_id::text, 0)
  );

  select to_jsonb(session_row)
  into stored_session
  from public.debate_sessions as session_row
  where session_row.id = requested_session_id;

  select to_jsonb(job_row)
  into stored_job
  from public.debate_jobs as job_row
  where job_row.id = requested_job_id;

  if stored_session is not null or stored_job is not null then
    if stored_session is not null
       and stored_job is not null
       and (stored_job ->> 'queue_message_id') is not null then
      return jsonb_build_object(
        'session', stored_session,
        'job', stored_job,
        'queue_message_id', (stored_job ->> 'queue_message_id')::bigint
      );
    end if;
    raise exception using
      errcode = '23505',
      message = 'Queued Debate admission is incomplete or conflicting';
  end if;

  insert into public.debate_sessions as inserted_session
  select (jsonb_populate_record(null::public.debate_sessions, session_payload)).*
  returning to_jsonb(inserted_session.*) into stored_session;

  insert into public.debate_jobs as inserted_job
  select (jsonb_populate_record(null::public.debate_jobs, job_payload)).*
  returning to_jsonb(inserted_job.*) into stored_job;

  select *
  into sent_queue_message_id
  from pgmq.send('debate_jobs', queue_payload, 0);

  update public.debate_jobs
  set queue_message_id = sent_queue_message_id
  where id = requested_job_id
  returning to_jsonb(public.debate_jobs.*) into stored_job;

  return jsonb_build_object(
    'session', stored_session,
    'job', stored_job,
    'queue_message_id', sent_queue_message_id
  );
end;
$$;

create or replace function public.enqueue_debate_round_two(
  intervention_payload jsonb,
  question_payload jsonb,
  session_payload jsonb,
  job_payload jsonb,
  queue_payload jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  requested_session_id uuid := (session_payload ->> 'id')::uuid;
  requested_job_id uuid := (job_payload ->> 'id')::uuid;
  requested_intervention_id uuid := (intervention_payload ->> 'id')::uuid;
  requested_question_id uuid := (question_payload ->> 'id')::uuid;
  current_session public.debate_sessions%rowtype;
  stored_session jsonb;
  stored_job jsonb;
  stored_intervention jsonb;
  stored_question jsonb;
  sent_queue_message_id bigint;
  queue_keys text[];
  expected_sequence integer;
begin
  select array_agg(key_name order by key_name)
  into queue_keys
  from jsonb_object_keys(queue_payload) as key_name;
  if queue_keys <> array[
    'enqueued_at',
    'job_id',
    'job_type',
    'schema_version',
    'session_id',
    'trace_id'
  ]::text[] then
    raise exception using
      errcode = '22023',
      message = 'Debate Queue payload must contain identifiers only';
  end if;
  if (queue_payload ->> 'schema_version')::integer <> 1
     or (queue_payload ->> 'job_id')::uuid <> requested_job_id
     or (queue_payload ->> 'session_id')::uuid <> requested_session_id
     or queue_payload ->> 'job_type' <> 'round_2'
     or queue_payload ->> 'trace_id' !~ '^[A-Za-z0-9_-]{8,80}$'
     or job_payload ->> 'job_type' <> 'round_2'
     or job_payload ->> 'status' <> 'queued'
     or job_payload -> 'queue_message_id' is distinct from 'null'::jsonb then
    raise exception using
      errcode = '22023',
      message = 'Queued Round 2 payloads do not match';
  end if;

  perform pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(requested_session_id::text, 0)
  );

  select to_jsonb(job_row)
  into stored_job
  from public.debate_jobs as job_row
  where job_row.id = requested_job_id;
  if stored_job is not null then
    select to_jsonb(session_row) into stored_session
    from public.debate_sessions as session_row
    where session_row.id = requested_session_id;
    select to_jsonb(intervention_row) into stored_intervention
    from public.debate_interventions as intervention_row
    where intervention_row.id = requested_intervention_id;
    select to_jsonb(question_row) into stored_question
    from public.debate_messages as question_row
    where question_row.id = requested_question_id;
    if stored_session is not null
       and stored_intervention is not null
       and stored_question is not null
       and (stored_job ->> 'queue_message_id') is not null then
      return jsonb_build_object(
        'session', stored_session,
        'job', stored_job,
        'intervention', stored_intervention,
        'question', stored_question,
        'queue_message_id', (stored_job ->> 'queue_message_id')::bigint
      );
    end if;
    raise exception using
      errcode = '23505',
      message = 'Queued Round 2 admission is incomplete or conflicting';
  end if;

  select * into current_session
  from public.debate_sessions
  where id = requested_session_id
    and user_id = (session_payload ->> 'user_id')::uuid
  for update;
  if not found or current_session.status <> 'awaiting_user' then
    raise exception using
      errcode = '23505',
      message = 'Debate Session is not awaiting Round 2 admission';
  end if;

  select coalesce(max(message_row.sequence_number), 0) + 1
  into expected_sequence
  from public.debate_messages as message_row
  where message_row.session_id = current_session.id
    and message_row.branch_id = current_session.active_branch_id;

  if intervention_payload ->> 'mode' <> 'challenge'
     or (intervention_payload ->> 'session_id')::uuid <> current_session.id
     or (intervention_payload ->> 'user_id')::uuid <> current_session.user_id
     or not exists (
       select 1
       from public.debate_messages as target
       where target.id = (intervention_payload ->> 'selected_message_id')::uuid
         and target.session_id = current_session.id
         and target.branch_id = current_session.active_branch_id
         and pg_catalog.strpos(
           target.content,
           intervention_payload ->> 'selected_text'
         ) > 0
     )
     or session_payload ->> 'status' <> 'queued_round_2'
     or (session_payload ->> 'active_branch_id')::uuid
       <> current_session.active_branch_id
     or (session_payload ->> 'active_generation_id')::uuid
       <> (question_payload ->> 'generation_id')::uuid
     or session_payload ->> 'ticker' <> current_session.ticker
     or session_payload ->> 'mode' <> current_session.mode
     or session_payload ->> 'opening_side' <> current_session.opening_side
     or (session_payload ->> 'stock_id')::bigint <> current_session.stock_id
     or session_payload ->> 'initial_question'
       is distinct from current_session.initial_question
     or session_payload -> 'analysis_context' <> current_session.analysis_context
     or session_payload -> 'factor_snapshot' <> current_session.factor_snapshot
     or (session_payload ->> 'interim_judge_message_id')::uuid
       is distinct from current_session.interim_judge_message_id
     or (session_payload ->> 'final_judge_message_id')::uuid
       is distinct from current_session.final_judge_message_id
     or session_payload ->> 'guardrail_status' <> current_session.guardrail_status
     or (session_payload ->> 'created_at')::timestamptz <> current_session.created_at
     or (session_payload ->> 'updated_at')::timestamptz < current_session.updated_at
     or (job_payload ->> 'session_id')::uuid <> current_session.id
     or (job_payload ->> 'user_id')::uuid <> current_session.user_id
     or (question_payload ->> 'session_id')::uuid <> current_session.id
     or (question_payload ->> 'branch_id')::uuid <> current_session.active_branch_id
     or (question_payload ->> 'sequence_number')::integer <> expected_sequence
     or (question_payload ->> 'round_number')::integer <> 2
     or (question_payload ->> 'exchange_number')::integer <> 0
     or question_payload ->> 'role' <> 'user'
     or question_payload ->> 'message_kind' <> 'question'
     or question_payload ->> 'content' <> intervention_payload ->> 'question'
     or question_payload -> 'metadata' ->> 'intervention_id'
       <> requested_intervention_id::text
     or question_payload -> 'metadata' ->> 'selected_message_id'
       <> intervention_payload ->> 'selected_message_id'
     or question_payload -> 'metadata' ->> 'selected_text'
       <> intervention_payload ->> 'selected_text'
     or question_payload -> 'metadata' ->> 'mode' <> 'challenge' then
    raise exception using
      errcode = '22023',
      message = 'Queued Round 2 records do not match canonical state';
  end if;

  insert into public.debate_interventions as inserted_intervention
  select (
    jsonb_populate_record(null::public.debate_interventions, intervention_payload)
  ).*
  returning to_jsonb(inserted_intervention.*) into stored_intervention;

  insert into public.debate_messages as inserted_question
  select (jsonb_populate_record(null::public.debate_messages, question_payload)).*
  returning to_jsonb(inserted_question.*) into stored_question;

  insert into public.debate_jobs as inserted_job
  select (jsonb_populate_record(null::public.debate_jobs, job_payload)).*
  returning to_jsonb(inserted_job.*) into stored_job;

  update public.debate_sessions as updated_session
  set status = 'queued_round_2',
      active_generation_id = (session_payload ->> 'active_generation_id')::uuid,
      updated_at = (session_payload ->> 'updated_at')::timestamptz
  where updated_session.id = current_session.id
  returning to_jsonb(updated_session.*) into stored_session;

  select * into sent_queue_message_id
  from pgmq.send('debate_jobs', queue_payload, 0);
  update public.debate_jobs
  set queue_message_id = sent_queue_message_id
  where id = requested_job_id
  returning to_jsonb(public.debate_jobs.*) into stored_job;

  return jsonb_build_object(
    'session', stored_session,
    'job', stored_job,
    'intervention', stored_intervention,
    'question', stored_question,
    'queue_message_id', sent_queue_message_id
  );
end;
$$;

create or replace function public.claim_debate_job(
  visibility_timeout_seconds integer default 900
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  claimed pgmq.message_record;
begin
  if visibility_timeout_seconds < 30 or visibility_timeout_seconds > 3600 then
    raise exception using
      errcode = '22023',
      message = 'Debate Queue visibility timeout is outside safe bounds';
  end if;

  select *
  into claimed
  from pgmq.read('debate_jobs', visibility_timeout_seconds, 1);

  if not found then
    return null;
  end if;

  return jsonb_build_object(
    'queue_message_id', claimed.msg_id,
    'read_count', claimed.read_ct,
    'enqueued_at', claimed.enqueued_at,
    'visibility_deadline', claimed.vt,
    'payload', claimed.message
  );
end;
$$;

create or replace function public.archive_debate_job(queue_message_id bigint)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  archived boolean;
begin
  if queue_message_id <= 0 then
    raise exception using
      errcode = '22023',
      message = 'Queue message identifier must be positive';
  end if;
  select pgmq.archive('debate_jobs', queue_message_id) into archived;
  return coalesce(archived, false);
end;
$$;

create or replace function public.retry_debate_job(
  queue_message_id bigint,
  delay_seconds integer
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  retried pgmq.message_record;
begin
  if queue_message_id <= 0 or delay_seconds < 0 or delay_seconds > 3600 then
    raise exception using
      errcode = '22023',
      message = 'Debate Queue retry arguments are outside safe bounds';
  end if;
  select *
  into retried
  from pgmq.set_vt('debate_jobs', queue_message_id, delay_seconds);
  return found;
end;
$$;

create or replace function public.requeue_debate_job(
  debate_job_id uuid,
  expected_attempt_count integer,
  observed_provider_request_count integer default 0,
  observed_prompt_tokens integer default 0,
  observed_completion_tokens integer default 0
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_job public.debate_jobs%rowtype;
  current_session public.debate_sessions%rowtype;
  queued_session_status text;
  changed_at timestamptz := statement_timestamp();
begin
  if expected_attempt_count < 1
     or observed_provider_request_count < 0
     or observed_prompt_tokens < 0
     or observed_completion_tokens < 0 then
    raise exception using
      errcode = '22023',
      message = 'Debate retry observations are outside safe bounds';
  end if;

  select * into current_job
  from public.debate_jobs
  where id = debate_job_id
  for update;
  if not found
     or current_job.status <> 'running'
     or current_job.attempt_count <> expected_attempt_count
     or current_job.attempt_count >= current_job.max_attempts
     or current_job.job_type not in ('round_1', 'round_2') then
    raise exception using
      errcode = '23505',
      message = 'Running Debate retry state changed concurrently';
  end if;

  select * into current_session
  from public.debate_sessions
  where id = current_job.session_id and user_id = current_job.user_id
  for update;
  queued_session_status := case current_job.job_type
    when 'round_1' then 'queued_round_1'
    else 'queued_round_2'
  end;
  if not found
     or current_session.status <> replace(queued_session_status, 'queued', 'running') then
    raise exception using
      errcode = '23505',
      message = 'Debate Session is not running the claimed Job';
  end if;

  update public.debate_jobs
  set status = 'queued',
      started_at = null,
      provider_request_count = greatest(
        current_job.provider_request_count,
        observed_provider_request_count
      ),
      prompt_tokens = greatest(current_job.prompt_tokens, observed_prompt_tokens),
      completion_tokens = greatest(
        current_job.completion_tokens,
        observed_completion_tokens
      ),
      total_tokens = greatest(current_job.prompt_tokens, observed_prompt_tokens)
        + greatest(current_job.completion_tokens, observed_completion_tokens),
      updated_at = greatest(changed_at, current_job.updated_at)
  where id = current_job.id
  returning * into current_job;

  update public.debate_sessions
  set status = queued_session_status,
      updated_at = greatest(changed_at, current_session.updated_at)
  where id = current_session.id
  returning * into current_session;

  return jsonb_build_object(
    'session', to_jsonb(current_session),
    'job', to_jsonb(current_job)
  );
end;
$$;

create or replace function public.fail_exhausted_debate_job(
  debate_job_id uuid,
  expected_attempt_count integer
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  current_job public.debate_jobs%rowtype;
  current_session public.debate_sessions%rowtype;
  expected_session_status text;
  changed_at timestamptz := statement_timestamp();
begin
  if expected_attempt_count < 1 then
    raise exception using
      errcode = '22023',
      message = 'Debate retry attempt is outside safe bounds';
  end if;

  select * into current_job
  from public.debate_jobs
  where id = debate_job_id
  for update;
  if not found
     or current_job.status <> 'running'
     or current_job.attempt_count <> expected_attempt_count
     or current_job.attempt_count < current_job.max_attempts
     or current_job.job_type not in ('round_1', 'round_2') then
    raise exception using
      errcode = '23505',
      message = 'Exhausted Debate Job state changed concurrently';
  end if;

  select * into current_session
  from public.debate_sessions
  where id = current_job.session_id and user_id = current_job.user_id
  for update;
  expected_session_status := case current_job.job_type
    when 'round_1' then 'running_round_1'
    else 'running_round_2'
  end;
  if not found or current_session.status <> expected_session_status then
    raise exception using
      errcode = '23505',
      message = 'Debate Session is not running the exhausted Job';
  end if;

  update public.debate_jobs
  set status = 'failed',
      finished_at = greatest(changed_at, current_job.updated_at),
      safe_error_code = 'debate_retry_exhausted',
      updated_at = greatest(changed_at, current_job.updated_at)
  where id = current_job.id
  returning * into current_job;

  update public.debate_sessions
  set status = 'failed',
      safe_error_code = 'debate_retry_exhausted',
      completed_at = greatest(changed_at, current_session.updated_at),
      updated_at = greatest(changed_at, current_session.updated_at)
  where id = current_session.id
  returning * into current_session;

  return jsonb_build_object(
    'session', to_jsonb(current_session),
    'job', to_jsonb(current_job)
  );
end;
$$;

revoke all on function public.enqueue_debate_session_job(jsonb, jsonb, jsonb)
  from public, anon, authenticated;
revoke all on function public.enqueue_debate_round_two(jsonb, jsonb, jsonb, jsonb, jsonb)
  from public, anon, authenticated;
revoke all on function public.claim_debate_job(integer)
  from public, anon, authenticated;
revoke all on function public.archive_debate_job(bigint)
  from public, anon, authenticated;
revoke all on function public.retry_debate_job(bigint, integer)
  from public, anon, authenticated;
revoke all on function public.requeue_debate_job(uuid, integer, integer, integer, integer)
  from public, anon, authenticated;
revoke all on function public.fail_exhausted_debate_job(uuid, integer)
  from public, anon, authenticated;

grant execute on function public.enqueue_debate_session_job(jsonb, jsonb, jsonb)
  to service_role;
grant execute on function public.enqueue_debate_round_two(jsonb, jsonb, jsonb, jsonb, jsonb)
  to service_role;
grant execute on function public.claim_debate_job(integer)
  to service_role;
grant execute on function public.archive_debate_job(bigint)
  to service_role;
grant execute on function public.retry_debate_job(bigint, integer)
  to service_role;
grant execute on function public.requeue_debate_job(uuid, integer, integer, integer, integer)
  to service_role;
grant execute on function public.fail_exhausted_debate_job(uuid, integer)
  to service_role;
