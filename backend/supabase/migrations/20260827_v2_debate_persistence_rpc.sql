-- Service-only transaction boundaries for canonical Debate persistence.
-- These functions do not enqueue durable Queue messages and are not callable by the
-- mobile/anon/authenticated roles.

create or replace function public.create_debate_session_with_job(
  session_payload jsonb,
  job_payload jsonb
)
returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  requested_session_id uuid := (session_payload ->> 'id')::uuid;
  requested_job_id uuid := (job_payload ->> 'id')::uuid;
  stored_session jsonb;
  stored_job jsonb;
begin
  select to_jsonb(session_row)
  into stored_session
  from public.debate_sessions as session_row
  where session_row.id = requested_session_id;

  select to_jsonb(job_row)
  into stored_job
  from public.debate_jobs as job_row
  where job_row.id = requested_job_id;

  if stored_session is not null or stored_job is not null then
    if stored_session is not null and stored_job is not null then
      return jsonb_build_object('session', stored_session, 'job', stored_job);
    end if;
    raise exception using
      errcode = '23505',
      message = 'Initial Debate persistence is incomplete or conflicting';
  end if;

  insert into public.debate_sessions as inserted_session
  select (jsonb_populate_record(null::public.debate_sessions, session_payload)).*
  returning to_jsonb(inserted_session.*) into stored_session;

  insert into public.debate_jobs as inserted_job
  select (jsonb_populate_record(null::public.debate_jobs, job_payload)).*
  returning to_jsonb(inserted_job.*) into stored_job;

  return jsonb_build_object('session', stored_session, 'job', stored_job);
end;
$$;

create or replace function public.append_debate_message(
  message_payload jsonb,
  citations_payload jsonb default '[]'::jsonb
)
returns jsonb
language plpgsql
set search_path = ''
as $$
declare
  requested_message_id uuid := (message_payload ->> 'id')::uuid;
  stored_message jsonb;
  stored_citations jsonb;
begin
  select to_jsonb(message_row)
  into stored_message
  from public.debate_messages as message_row
  where message_row.id = requested_message_id;

  if stored_message is null then
    insert into public.debate_messages as inserted_message
    select (jsonb_populate_record(null::public.debate_messages, message_payload)).*
    returning to_jsonb(inserted_message.*) into stored_message;

    insert into public.debate_message_evidence
    select citation_row.*
    from jsonb_populate_recordset(
      null::public.debate_message_evidence,
      citations_payload
    ) as citation_row;
  end if;

  select coalesce(
    jsonb_agg(to_jsonb(evidence_row) order by evidence_row.citation_order),
    '[]'::jsonb
  )
  into stored_citations
  from public.debate_message_evidence as evidence_row
  where evidence_row.message_id = requested_message_id;

  return jsonb_build_object(
    'message', stored_message,
    'citations', stored_citations
  );
end;
$$;

revoke all on function public.create_debate_session_with_job(jsonb, jsonb)
  from public, anon, authenticated;
revoke all on function public.append_debate_message(jsonb, jsonb)
  from public, anon, authenticated;

grant execute on function public.create_debate_session_with_job(jsonb, jsonb)
  to service_role;
grant execute on function public.append_debate_message(jsonb, jsonb)
  to service_role;
