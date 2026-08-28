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

revoke all on function public.enqueue_debate_session_job(jsonb, jsonb, jsonb)
  from public, anon, authenticated;
revoke all on function public.claim_debate_job(integer)
  from public, anon, authenticated;
revoke all on function public.archive_debate_job(bigint)
  from public, anon, authenticated;
revoke all on function public.retry_debate_job(bigint, integer)
  from public, anon, authenticated;

grant execute on function public.enqueue_debate_session_job(jsonb, jsonb, jsonb)
  to service_role;
grant execute on function public.claim_debate_job(integer)
  to service_role;
grant execute on function public.archive_debate_job(bigint)
  to service_role;
grant execute on function public.retry_debate_job(bigint, integer)
  to service_role;
