-- Distinguish a resumable interruption from terminal cancellation.
alter table public.debate_sessions drop constraint if exists debate_sessions_status_check;
alter table public.debate_sessions add constraint debate_sessions_status_check check (status in (
  'created','queued_round_1','running_round_1','awaiting_user','queued_round_2',
  'running_round_2','completed','cancel_requested','cancelled','failed',
  'interrupted_awaiting_user'
));

-- Default-off Stop foundation. Apply before DEBATE_INTERRUPTIONS_ENABLED.
-- Server-only checkpoints are written before deltas become visible to clients.
create table if not exists public.debate_draft_checkpoints (
  message_id uuid primary key,
  session_id uuid not null references public.debate_sessions(id) on delete cascade,
  payload jsonb not null check (jsonb_typeof(payload) = 'object'),
  check (jsonb_typeof(payload -> 'content') = 'string' and payload ? 'content'
    and char_length(payload ->> 'content') <= 6000)
);
create index if not exists debate_draft_checkpoints_session_idx
  on public.debate_draft_checkpoints(session_id);
alter table public.debate_draft_checkpoints enable row level security;
revoke all on public.debate_draft_checkpoints from public, anon, authenticated;
grant all on public.debate_draft_checkpoints to service_role;

create or replace function public.checkpoint_debate_draft(message_payload jsonb)
returns void language plpgsql set search_path = '' as $$
declare
  s public.debate_sessions%rowtype;
  previous jsonb;
  mid uuid := (message_payload ->> 'id')::uuid;
begin
  select * into s from public.debate_sessions
    where id = (message_payload ->> 'session_id')::uuid for update;
  if not found or s.status not in ('running_round_1', 'running_round_2')
     or (message_payload ->> 'generation_id')::uuid is distinct from s.active_generation_id
     or (message_payload ->> 'branch_id')::uuid is distinct from s.active_branch_id
     or coalesce(message_payload ->> 'role','') not in ('bull','bear','judge')
     or message_payload ->> 'message_kind' is null
     or message_payload ->> 'exchange_number' is null
     or ((message_payload ->> 'role') in ('bull','bear')
         and (message_payload ->> 'message_kind') not in ('argument','rebuttal'))
     or ((message_payload ->> 'role') = 'judge'
         and ((message_payload ->> 'message_kind') <> 'summary'
              or (message_payload ->> 'exchange_number')::integer is distinct from 0))
     or (message_payload ->> 'sequence_number')::integer is null
     or (message_payload ->> 'sequence_number')::integer < 1
     or (message_payload ->> 'round_number')::integer is distinct from
        (case when s.status='running_round_1' then 1 else 2 end) then
    raise exception using errcode='PT409', message='Draft generation is not active';
  end if;
  if exists (
    select 1 from public.debate_messages
      where session_id=s.id and branch_id=s.active_branch_id
        and sequence_number=(message_payload ->> 'sequence_number')::integer
        and id <> (message_payload ->> 'id')::uuid
  ) then
    raise exception using errcode='PT409', message='Draft sequence is already canonical';
  end if;
  select payload into previous from public.debate_draft_checkpoints where message_id=mid;
  if previous is not null and (
    previous ->> 'session_id' is distinct from message_payload ->> 'session_id'
    or previous ->> 'generation_id' is distinct from message_payload ->> 'generation_id'
    or previous ->> 'branch_id' is distinct from message_payload ->> 'branch_id'
    or previous ->> 'sequence_number' is distinct from message_payload ->> 'sequence_number'
    or left(message_payload ->> 'content', char_length(previous ->> 'content'))
       is distinct from previous ->> 'content') then
    raise exception using errcode='PT409', message='Draft prefix changed';
  end if;
  insert into public.debate_draft_checkpoints(message_id,session_id,payload)
    values(mid,s.id,message_payload)
    on conflict(message_id) do update set payload=excluded.payload;
end; $$;

create or replace function public.interrupt_debate_generation(
  requested_session_id uuid, requested_user_id uuid, requested_generation_id uuid,
  requested_message_id uuid, visible_prefix text, interrupted_at timestamptz
) returns jsonb language plpgsql set search_path = '' as $$
declare
  s public.debate_sessions%rowtype;
  target jsonb;
  target_sequence integer;
  result jsonb;
begin
  select * into s from public.debate_sessions
    where id=requested_session_id and user_id=requested_user_id for update;
  if not found then
    raise exception using errcode='PT409', message='Interruption target unavailable';
  end if;
  select to_jsonb(m) into target from public.debate_messages m where id=requested_message_id;
  if target is null then
    select payload into target from public.debate_draft_checkpoints where message_id=requested_message_id;
  end if;
  if target is null or (target ->> 'session_id')::uuid is distinct from s.id
      or (target ->> 'branch_id')::uuid is distinct from s.active_branch_id then
    raise exception using errcode='PT409', message='Interruption target unavailable';
  end if;
  if s.status='interrupted_awaiting_user' and target ->> 'is_complete'='false'
      and target #>> '{metadata,interrupted}'='true'
      and (target ->> 'generation_id')::uuid=requested_generation_id
      and target ->> 'content'=visible_prefix then
    return to_jsonb(s);
  end if;
  if s.status in ('cancelled','cancel_requested','failed','interrupted_awaiting_user')
      or s.active_generation_id is distinct from requested_generation_id
      or (target ->> 'generation_id')::uuid is distinct from requested_generation_id
      or target ->> 'role' not in ('bull','bear','judge')
      or visible_prefix is null or char_length(visible_prefix)>6000
      or left(target ->> 'content',char_length(visible_prefix)) is distinct from visible_prefix then
    raise exception using errcode='PT409', message='Interruption prefix or generation is invalid';
  end if;
  interrupted_at := greatest(interrupted_at,s.updated_at);
  target_sequence := (target ->> 'sequence_number')::integer;
  target := target || jsonb_build_object('content',visible_prefix,'is_complete',false,
    'cancelled_at',interrupted_at,'confidence',null,'signal_strength',null,'terms','[]'::jsonb,
    'metadata',jsonb_build_object('interrupted',true));
  -- Same session lock is held by canonical append RPCs: completion cannot race
  -- this prefix replacement, generation rotation and later-message removal.
  delete from public.debate_messages where session_id=s.id and branch_id=s.active_branch_id
    and sequence_number>=target_sequence;
  insert into public.debate_messages
    select (jsonb_populate_record(null::public.debate_messages,target)).*;
  delete from public.debate_draft_checkpoints where session_id=s.id;
  -- Running worker acknowledges cancellation and records its observed usage.
  update public.debate_jobs set status='cancelled',finished_at=greatest(interrupted_at,updated_at),
    updated_at=greatest(interrupted_at,updated_at) where session_id=s.id and status='queued';
  update public.debate_sessions set status='interrupted_awaiting_user',active_generation_id=gen_random_uuid(),
    updated_at=interrupted_at,completed_at=null,final_judge_message_id=null,
    interim_judge_message_id=case when exists(select 1 from public.debate_messages
      where id=s.interim_judge_message_id and sequence_number<target_sequence)
      then s.interim_judge_message_id else null end
    where id=s.id returning to_jsonb(debate_sessions.*) into result;
  return result;
end; $$;
revoke all on function public.checkpoint_debate_draft(jsonb) from public,anon,authenticated;
revoke all on function public.interrupt_debate_generation(uuid,uuid,uuid,uuid,text,timestamptz) from public,anon,authenticated;
grant execute on function public.checkpoint_debate_draft(jsonb) to service_role;
grant execute on function public.interrupt_debate_generation(uuid,uuid,uuid,uuid,text,timestamptz) to service_role;

-- Retain only in-flight checkpoints; canonical output supersedes its draft.
create or replace function public.prune_debate_draft_checkpoint()
returns trigger language plpgsql set search_path = '' as $$
begin
  if tg_table_name='debate_messages' then
    delete from public.debate_draft_checkpoints where message_id=new.id;
  elsif tg_table_name='debate_sessions' and new.status in ('completed','cancelled','failed') then
    delete from public.debate_draft_checkpoints where session_id=new.id;
  elsif tg_table_name='debate_jobs' and new.status='queued' then
    -- A retry starts a fresh provider request for the first unfinished turn.
    -- Its old output is not a valid prefix for that request, while the
    -- provider-attempt ledger remains available for billing/audit settlement.
    delete from public.debate_draft_checkpoints where session_id=new.session_id;
  end if;
  return new;
end; $$;
revoke all on function public.prune_debate_draft_checkpoint() from public,anon,authenticated;
drop trigger if exists prune_canonical_debate_draft on public.debate_messages;
create trigger prune_canonical_debate_draft after insert on public.debate_messages
  for each row execute function public.prune_debate_draft_checkpoint();
drop trigger if exists prune_terminal_debate_drafts on public.debate_sessions;
create trigger prune_terminal_debate_drafts after update of status on public.debate_sessions
  for each row execute function public.prune_debate_draft_checkpoint();
drop trigger if exists prune_retried_debate_drafts on public.debate_jobs;
create trigger prune_retried_debate_drafts after update of status on public.debate_jobs
  for each row execute function public.prune_debate_draft_checkpoint();

-- Saving a point changes the transcript only; it never enqueues provider work.
create or replace function public.record_debate_interjection(message_payload jsonb)
returns jsonb language plpgsql set search_path='' as $$
declare s public.debate_sessions%rowtype; target public.debate_messages%rowtype;
  existing public.debate_messages%rowtype; result jsonb;
begin
  select * into s from public.debate_sessions where id=(message_payload->>'session_id')::uuid for update;
  if not found then
    raise exception using errcode='PT409', message='Debate is not waiting at this interruption';
  end if;
  -- Preserve exact retries even after Continue or End wins the state race.
  select * into existing from public.debate_messages where id=(message_payload->>'id')::uuid;
  if found then
    if existing.session_id<>s.id
      or existing.branch_id is distinct from (message_payload->>'branch_id')::uuid
      or existing.generation_id is distinct from (message_payload->>'generation_id')::uuid
      or existing.role is distinct from message_payload->>'role'
      or existing.message_kind is distinct from message_payload->>'message_kind'
      or existing.content is distinct from message_payload->>'content'
      or existing.metadata is distinct from message_payload->'metadata' then
      raise exception using errcode='PT409', message='Interjection key conflicts';
    end if;
    return to_jsonb(existing);
  end if;
  if s.status<>'interrupted_awaiting_user'
    or s.active_generation_id is distinct from (message_payload->>'generation_id')::uuid
    or s.active_branch_id is distinct from (message_payload->>'branch_id')::uuid then
    raise exception using errcode='PT409', message='Debate is not waiting at this interruption';
  end if;
  select * into target from public.debate_messages where session_id=s.id and branch_id=s.active_branch_id
    and not is_complete and metadata->>'interrupted'='true' order by sequence_number desc limit 1;
  if not found or target.role not in ('bull','bear','judge')
    or message_payload#>>'{metadata,interrupted_message_id}' is distinct from target.id::text
    or message_payload->>'role' is distinct from 'user'
    or message_payload->>'message_kind' is distinct from 'question'
    or message_payload#>>'{metadata,interjection}' is distinct from 'true'
    or coalesce(char_length(btrim(message_payload->>'content')),0) not between 1 and 500
    or (message_payload->>'round_number')::integer is distinct from target.round_number
    or (message_payload->>'is_complete')::boolean is distinct from true then
    raise exception using errcode='PT409', message='Invalid interjection target';
  end if;
  if (select count(*) from public.debate_messages where session_id=s.id and branch_id=s.active_branch_id
      and metadata->>'interjection'='true')>=6
    or (message_payload->>'sequence_number')::integer is distinct from
      (select coalesce(max(sequence_number),0)+1 from public.debate_messages where session_id=s.id and branch_id=s.active_branch_id) then
    raise exception using errcode='PT409', message='Interjection limit or sequence conflict';
  end if;
  insert into public.debate_messages select (jsonb_populate_record(null::public.debate_messages,message_payload)).*
    returning to_jsonb(debate_messages.*) into result;
  update public.debate_sessions set updated_at=greatest(updated_at,(message_payload->>'created_at')::timestamptz) where id=s.id;
  return result;
end; $$;
revoke all on function public.record_debate_interjection(jsonb) from public,anon,authenticated;
grant execute on function public.record_debate_interjection(jsonb) to service_role;

-- Explicit Continue is one transaction: state rotation, job ledger and Queue.
create or replace function public.continue_interrupted_debate(
  session_payload jsonb, job_payload jsonb, queue_payload jsonb,
  expected_generation_id uuid, requested_interjection_id uuid
) returns jsonb language plpgsql security definer set search_path='' as $$
declare s public.debate_sessions%rowtype; point public.debate_messages%rowtype;
  target public.debate_messages%rowtype; existing public.debate_jobs%rowtype;
  saved_session jsonb; saved_job jsonb; queue_id bigint; stamp timestamptz;
begin
  select * into s from public.debate_sessions where id=(session_payload->>'id')::uuid
    and user_id=(session_payload->>'user_id')::uuid for update;
  if not found then raise exception using errcode='PT409', message='Session unavailable'; end if;
  if expected_generation_id is null or requested_interjection_id is null
    or coalesce(job_payload->>'idempotency_key','') !~
      ('^continue:'||s.id::text||':'||expected_generation_id::text||':'||requested_interjection_id::text||':[A-Za-z0-9_-]{8,80}$') then
    raise exception using errcode='PT409', message='Continue key is not bound to the interruption';
  end if;
  select * into existing from public.debate_jobs where id=(job_payload->>'id')::uuid;
  if found then
    if existing.session_id<>s.id or existing.user_id<>s.user_id
      or existing.idempotency_key is distinct from job_payload->>'idempotency_key' then
      raise exception using errcode='PT409', message='Continue key conflicts';
    end if;
    return jsonb_build_object('session',to_jsonb(s),'job',to_jsonb(existing));
  end if;
  if s.status<>'interrupted_awaiting_user' or s.active_generation_id<>expected_generation_id
    or (session_payload->>'active_generation_id')::uuid=s.active_generation_id
    or (session_payload->>'active_branch_id')::uuid is distinct from s.active_branch_id
    or session_payload->'analysis_context' is distinct from s.analysis_context
    or session_payload->'factor_snapshot' is distinct from s.factor_snapshot then
    raise exception using errcode='PT409', message='Debate is not waiting at this interruption';
  end if;
  stamp := (session_payload->>'updated_at')::timestamptz;
  if stamp is null or stamp < s.updated_at or stamp > least(s.created_at,coalesce((s.analysis_context->>'captured_at')::timestamptz,s.created_at)) + interval '30 minutes' then
    raise exception using errcode='PT409', message='Frozen discussion expired';
  end if;
  select * into target from public.debate_messages where session_id=s.id and branch_id=s.active_branch_id
    and not is_complete and metadata->>'interrupted'='true' order by sequence_number desc limit 1;
  select * into point from public.debate_messages where id=requested_interjection_id;
  if target.id is null or target.role not in ('bull','bear','judge')
    or point.id is null or point.session_id<>s.id or point.branch_id<>s.active_branch_id
    or point.generation_id<>expected_generation_id or point.role<>'user'
    or point.message_kind<>'question' or not point.is_complete or btrim(point.content)=''
    or point.metadata->>'interjection' is distinct from 'true'
    or point.metadata->>'interrupted_message_id' is distinct from target.id::text
    or point.sequence_number<=target.sequence_number
    or exists(select 1 from public.debate_messages where session_id=s.id and branch_id=s.active_branch_id and sequence_number>point.sequence_number)
    or session_payload->>'status' is distinct from 'queued_round_'||target.round_number
    or job_payload->>'job_type' is distinct from 'round_'||target.round_number
    or (job_payload->>'session_id')::uuid is distinct from s.id
    or (job_payload->>'user_id')::uuid is distinct from s.user_id
    or job_payload->>'status' is distinct from 'queued'
    or queue_payload->>'job_id' is distinct from job_payload->>'id'
    or queue_payload->>'session_id' is distinct from s.id::text
    or queue_payload->>'job_type' is distinct from job_payload->>'job_type' then
    raise exception using errcode='PT409', message='Invalid Continue point or job';
  end if;
  insert into public.debate_jobs select (jsonb_populate_record(null::public.debate_jobs,job_payload)).*;
  update public.debate_sessions set status=session_payload->>'status',
    active_generation_id=(session_payload->>'active_generation_id')::uuid,updated_at=stamp
    where id=s.id returning to_jsonb(debate_sessions.*) into saved_session;
  select * into queue_id from pgmq.send('debate_jobs',queue_payload,0);
  update public.debate_jobs set queue_message_id=queue_id where id=(job_payload->>'id')::uuid
    returning to_jsonb(debate_jobs.*) into saved_job;
  return jsonb_build_object('session',saved_session,'job',saved_job);
end; $$;
revoke all on function public.continue_interrupted_debate(jsonb,jsonb,jsonb,uuid,uuid) from public,anon,authenticated;
grant execute on function public.continue_interrupted_debate(jsonb,jsonb,jsonb,uuid,uuid) to service_role;
create or replace function public.interrupt_debate_before_output_generation(
  requested_session_id uuid,
  requested_user_id uuid,
  requested_generation_id uuid,
  interrupted_at timestamptz
) returns jsonb language plpgsql set search_path = '' as $$
declare
  s public.debate_sessions%rowtype;
  existing_message public.debate_messages%rowtype;
  existing_draft public.debate_draft_checkpoints%rowtype;
  anchor_role text;
  round_number integer;
  anchor_sequence integer;
  stamp timestamptz;
  result jsonb;
begin
  -- Provider admission, canonical append and this operation all lock the
  -- session row. This lock is the before-output linearization point.
  select * into s from public.debate_sessions
    where id=requested_session_id and user_id=requested_user_id for update;
  if not found then
    raise exception using errcode='PT409', message='Before-output interruption target unavailable';
  end if;

  -- The generation UUID is also the stable empty anchor id. A retry after the
  -- generation rotation finds this row and returns the same stopped session.
  select * into existing_message from public.debate_messages where id=requested_generation_id;
  if found then
    if existing_message.session_id <> s.id then
      raise exception using errcode='PT409', message='Before-output anchor identifier collision';
    end if;
    if s.status='interrupted_awaiting_user'
       and existing_message.generation_id=requested_generation_id
       and existing_message.branch_id=s.active_branch_id
       and existing_message.role in ('bull','bear','judge')
       and existing_message.content=''
       and not existing_message.is_complete
       and existing_message.metadata->>'interrupted'='true'
       and existing_message.metadata->>'before_output'='true' then
      return to_jsonb(s);
    end if;
    raise exception using errcode='PT409', message='Before-output anchor identifier already exists';
  end if;

  select * into existing_draft from public.debate_draft_checkpoints
    where message_id=requested_generation_id;
  if found and (existing_draft.session_id <> s.id
                or (existing_draft.payload->>'generation_id')::uuid is distinct from requested_generation_id) then
    raise exception using errcode='PT409', message='Before-output anchor identifier collision';
  end if;

  if s.status not in ('queued_round_1','queued_round_2','running_round_1','running_round_2')
     or s.active_generation_id is distinct from requested_generation_id then
    raise exception using errcode='PT409', message='Debate generation is not waiting before output';
  end if;

  -- User challenge/question rows are part of the generation but are not
  -- agent output. Only non-empty agent canonical/draft text rejects the stop.
  if exists (
    select 1 from public.debate_messages
      where session_id=s.id and branch_id=s.active_branch_id
        and generation_id=requested_generation_id
        and role in ('bull','bear','judge') and content <> ''
  ) or exists (
    select 1 from public.debate_draft_checkpoints
      where session_id=s.id
        and (payload->>'generation_id')::uuid=requested_generation_id
        and coalesce(payload->>'content','') <> ''
  ) then
    raise exception using errcode='PT409', message='Debate generation has already produced output';
  end if;

  round_number := case when s.status in ('queued_round_1','running_round_1') then 1 else 2 end;
  anchor_role := s.opening_side;
  stamp := greatest(interrupted_at, s.updated_at);
  select coalesce(max(sequence_number),0)+1 into anchor_sequence
    from public.debate_messages
    where session_id=s.id and branch_id=s.active_branch_id;

  insert into public.debate_messages(
    id, session_id, branch_id, generation_id, sequence_number,
    round_number, exchange_number, role, message_kind, content,
    confidence, signal_strength, terms, metadata, is_complete,
    cancelled_at, created_at
  ) values (
    requested_generation_id, s.id, s.active_branch_id, requested_generation_id,
    anchor_sequence, round_number, 1, anchor_role, 'argument', '',
    null, null, '{}'::text[], jsonb_build_object('interrupted',true,'before_output',true),
    false, stamp, stamp
  );

  -- Queued delivery is safe to cancel immediately. A running worker observes
  -- the rotated generation and settles its job after its in-flight call.
  update public.debate_jobs
    set status='cancelled', finished_at=greatest(stamp,updated_at), updated_at=greatest(stamp,updated_at)
    where session_id=s.id and status='queued';
  delete from public.debate_draft_checkpoints where session_id=s.id;

  update public.debate_sessions
    set status='interrupted_awaiting_user', active_generation_id=gen_random_uuid(),
      updated_at=stamp, completed_at=null, final_judge_message_id=null
    where id=s.id
    returning to_jsonb(debate_sessions.*) into result;
  return result;
end; $$;

revoke all on function public.interrupt_debate_before_output_generation(uuid,uuid,uuid,timestamptz)
  from public, anon, authenticated;
grant execute on function public.interrupt_debate_before_output_generation(uuid,uuid,uuid,timestamptz)
  to service_role;
create table if not exists public.debate_provider_attempts (
  id uuid primary key,
  session_id uuid not null references public.debate_sessions(id) on delete cascade,
  generation_id uuid not null,
  message_id uuid not null,
  role text not null check (role in ('bull','bear','judge')),
  provider text not null check (char_length(provider) between 1 and 120),
  model text not null check (char_length(model) between 1 and 160),
  admitted_at timestamptz not null,
  dispatched_at timestamptz,
  finished_at timestamptz,
  outcome text not null default 'admitted'
    check (outcome in ('admitted','dispatched','completed','failed')),
  usage_status text not null default 'unknown'
    check (usage_status in ('unknown','reported')),
  prompt_tokens bigint check (prompt_tokens >= 0),
  completion_tokens bigint check (completion_tokens >= 0),
  total_tokens bigint check (total_tokens >= 0),
  constraint debate_provider_attempt_lifecycle check (
    (outcome='admitted' and dispatched_at is null and finished_at is null)
    or (outcome='dispatched' and dispatched_at is not null and finished_at is null)
    or (outcome in ('completed','failed') and dispatched_at is not null and finished_at is not null)
  ),
  constraint debate_provider_attempt_timing check (
    (dispatched_at is null or dispatched_at >= admitted_at)
    and (finished_at is null or (dispatched_at is not null and finished_at >= dispatched_at))
  ),
  constraint debate_provider_attempt_usage check (
    (usage_status='unknown' and prompt_tokens is null and completion_tokens is null and total_tokens is null)
    or (usage_status='reported' and prompt_tokens is not null and completion_tokens is not null
      and total_tokens = prompt_tokens + completion_tokens)
  )
);

create index if not exists debate_provider_attempts_session_idx
  on public.debate_provider_attempts(session_id, admitted_at, id);

alter table public.debate_provider_attempts enable row level security;
revoke all on public.debate_provider_attempts from public, anon, authenticated;
grant all on public.debate_provider_attempts to service_role;

-- Admission serializes with Stop and with ordinary draft checkpoints by
-- locking the session. It inserts the audit row and an empty checkpoint in
-- the same transaction, so a request cannot become billable without a
-- resumable draft identity.
create or replace function public.admit_debate_provider_attempt(
  attempt_payload jsonb, checkpoint_payload jsonb
) returns jsonb language plpgsql set search_path='' as $$
declare
  s public.debate_sessions%rowtype;
  stored public.debate_provider_attempts%rowtype;
  existing public.debate_provider_attempts%rowtype;
  existing_checkpoint jsonb;
  expected_round integer;
  requested_id uuid;
begin
  if jsonb_typeof(attempt_payload) is distinct from 'object'
     or jsonb_typeof(checkpoint_payload) is distinct from 'object'
     or attempt_payload->>'id' is null
     or attempt_payload->>'session_id' is null
     or attempt_payload->>'generation_id' is null
     or attempt_payload->>'message_id' is null
     or attempt_payload->>'role' is null
     or attempt_payload->>'provider' is null
     or attempt_payload->>'model' is null
     or attempt_payload->>'admitted_at' is null
     or checkpoint_payload->>'message_id' is null
     or checkpoint_payload->>'session_id' is null
     or checkpoint_payload->>'generation_id' is null
     or checkpoint_payload->>'branch_id' is null
     or checkpoint_payload->>'sequence_number' is null
     or checkpoint_payload->>'round_number' is null
     or checkpoint_payload->>'role' is null
     or checkpoint_payload->>'message_kind' is null
     or checkpoint_payload->>'content' is null then
    raise exception using errcode='PT409', message='Provider attempt payload is invalid';
  end if;

  requested_id := (attempt_payload->>'id')::uuid;
  select * into s
    from public.debate_sessions
    where id=(attempt_payload->>'session_id')::uuid
    for update;
  if not found then
    raise exception using errcode='PT409', message='Provider attempt generation is not active';
  end if;

  -- A provider admission can be retried after Stop has rotated the session.
  -- Return the exact durable identity before checking the now-stale active
  -- generation; a changed identity remains a conflict.
  select * into existing
    from public.debate_provider_attempts
    where id=requested_id
    for update;
  if found then
    if attempt_payload->>'outcome' is distinct from 'admitted'
       or attempt_payload->>'usage_status' is distinct from 'unknown'
       or attempt_payload ? 'dispatched_at' and attempt_payload->>'dispatched_at' is not null
       or attempt_payload ? 'finished_at' and attempt_payload->>'finished_at' is not null
       or attempt_payload->>'prompt_tokens' is not null
       or attempt_payload->>'completion_tokens' is not null
       or attempt_payload->>'total_tokens' is not null
       or checkpoint_payload->>'content' is distinct from ''
       or existing.session_id is distinct from s.id
       or existing.generation_id is distinct from (attempt_payload->>'generation_id')::uuid
       or existing.message_id is distinct from (attempt_payload->>'message_id')::uuid
       or existing.message_id is distinct from (checkpoint_payload->>'message_id')::uuid
       or existing.role is distinct from attempt_payload->>'role'
       or existing.provider is distinct from attempt_payload->>'provider'
       or existing.model is distinct from attempt_payload->>'model'
       or existing.admitted_at is distinct from (attempt_payload->>'admitted_at')::timestamptz
       or checkpoint_payload->>'session_id' is distinct from existing.session_id::text
       or checkpoint_payload->>'generation_id' is distinct from existing.generation_id::text
       or checkpoint_payload->>'role' is distinct from existing.role then
      raise exception using errcode='PT409', message='Provider attempt identifier conflict';
    end if;
    return to_jsonb(existing);
  end if;
  expected_round := case when s.status='running_round_1' then 1
                         when s.status='running_round_2' then 2 else null end;
  if expected_round is null
     or attempt_payload->>'outcome' is distinct from 'admitted'
     or attempt_payload->>'usage_status' is distinct from 'unknown'
     or attempt_payload ? 'dispatched_at' and attempt_payload->>'dispatched_at' is not null
     or attempt_payload ? 'finished_at' and attempt_payload->>'finished_at' is not null
     or (attempt_payload->>'session_id')::uuid is distinct from s.id
     or (attempt_payload->>'generation_id')::uuid is distinct from s.active_generation_id
     or attempt_payload->>'role' not in ('bull','bear','judge')
     or char_length(attempt_payload->>'provider') not between 1 and 120
     or char_length(attempt_payload->>'model') not between 1 and 160
     or attempt_payload->>'message_id' is distinct from checkpoint_payload->>'message_id'
     or checkpoint_payload->>'session_id' is distinct from attempt_payload->>'session_id'
     or checkpoint_payload->>'generation_id' is distinct from attempt_payload->>'generation_id'
     or (checkpoint_payload->>'branch_id')::uuid is distinct from s.active_branch_id
     or (checkpoint_payload->>'round_number')::integer is distinct from expected_round
     or (checkpoint_payload->>'sequence_number')::integer < 1
     or checkpoint_payload->>'content' is distinct from ''
     or checkpoint_payload->>'role' is distinct from attempt_payload->>'role'
     or (
       attempt_payload->>'role'='judge'
       and ((checkpoint_payload->>'exchange_number')::integer is distinct from 0
         or checkpoint_payload->>'message_kind' is distinct from 'summary')
     )
     or (
       attempt_payload->>'role' in ('bull','bear')
       and ((checkpoint_payload->>'exchange_number')::integer is null
         or (checkpoint_payload->>'exchange_number')::integer not between 1 and 3
         or checkpoint_payload->>'message_kind' not in ('argument','rebuttal'))
     )
     or attempt_payload->>'prompt_tokens' is not null
     or attempt_payload->>'completion_tokens' is not null
     or attempt_payload->>'total_tokens' is not null then
    raise exception using errcode='PT409', message='Provider attempt generation is not active';
  end if;

  -- A canonical row or another in-flight checkpoint already owns this
  -- message/sequence. The same-id retry was handled above.
  if exists (
    select 1 from public.debate_messages
    where id=(attempt_payload->>'message_id')::uuid
       or (session_id=s.id and branch_id=s.active_branch_id
           and sequence_number=(checkpoint_payload->>'sequence_number')::integer)
  ) or exists (
    select 1 from public.debate_draft_checkpoints
    where session_id=s.id
      and payload->>'branch_id'=s.active_branch_id::text
      and (payload->>'sequence_number')::integer=(checkpoint_payload->>'sequence_number')::integer
      and message_id <> (attempt_payload->>'message_id')::uuid
  ) then
    raise exception using errcode='PT409', message='Provider attempt message is already reserved';
  end if;

  insert into public.debate_provider_attempts
    select (jsonb_populate_record(null::public.debate_provider_attempts,attempt_payload)).*
    on conflict (id) do nothing
    returning * into stored;
  if not found then
    -- This can only happen when the same id was admitted concurrently for a
    -- different session, which is still a conflict after the session lock.
    select * into stored from public.debate_provider_attempts
      where id=requested_id for update;
    if not found
       or stored.session_id <> s.id
       or stored.generation_id <> (attempt_payload->>'generation_id')::uuid
       or stored.message_id <> (attempt_payload->>'message_id')::uuid
       or stored.role <> attempt_payload->>'role'
       or stored.provider <> attempt_payload->>'provider'
       or stored.model <> attempt_payload->>'model'
       or stored.admitted_at <> (attempt_payload->>'admitted_at')::timestamptz then
      raise exception using errcode='PT409', message='Provider attempt identifier conflict';
    end if;
    return to_jsonb(stored);
  end if;

  checkpoint_payload := (checkpoint_payload - 'message_id') || jsonb_build_object(
    'id',attempt_payload->>'message_id',
    'is_complete',false,
    'cancelled_at',null,
    'confidence',null,
    'signal_strength',null,
    'terms','[]'::jsonb,
    'metadata','{}'::jsonb
  );
  select payload into existing_checkpoint
    from public.debate_draft_checkpoints
    where message_id=stored.message_id
    for update;
  if existing_checkpoint is null then
    insert into public.debate_draft_checkpoints(message_id,session_id,payload)
      values(stored.message_id,stored.session_id,checkpoint_payload)
      on conflict (message_id) do nothing;
  elsif existing_checkpoint->>'session_id' is distinct from stored.session_id::text
     or existing_checkpoint->>'generation_id' is distinct from stored.generation_id::text
     or existing_checkpoint->>'branch_id' is distinct from checkpoint_payload->>'branch_id'
     or existing_checkpoint->>'sequence_number' is distinct from checkpoint_payload->>'sequence_number'
     or existing_checkpoint->>'content' is distinct from '' then
    raise exception using errcode='PT409', message='Provider checkpoint identifier conflict';
  end if;
  return to_jsonb(stored);
end; $$;

create or replace function public.dispatch_debate_provider_attempt(
  requested_attempt_id uuid, dispatched_at timestamptz
) returns jsonb language plpgsql set search_path='' as $$
declare result jsonb;
begin
  update public.debate_provider_attempts as attempt set
    outcome='dispatched', dispatched_at=dispatch_debate_provider_attempt.dispatched_at
    where attempt.id=requested_attempt_id and attempt.outcome='admitted'
      and dispatch_debate_provider_attempt.dispatched_at >= attempt.admitted_at
    returning to_jsonb(attempt.*) into result;
  if result is null then
    raise exception using errcode='PT409', message='Provider attempt is not dispatchable';
  end if;
  return result;
end; $$;

create or replace function public.finish_debate_provider_attempt(
  requested_attempt_id uuid, finished_at timestamptz,
  reported_prompt_tokens bigint default null,
  reported_completion_tokens bigint default null,
  reported_total_tokens bigint default null,
  attempt_failed boolean default false
) returns jsonb language plpgsql set search_path='' as $$
declare
  result jsonb;
  reported boolean := reported_prompt_tokens is not null
    and reported_completion_tokens is not null
    and reported_total_tokens is not null;
begin
  update public.debate_provider_attempts as attempt set
    -- Late callbacks may settle usage, but cannot change the first terminal
    -- outcome from completed to failed (or failed to completed).
    outcome=case
      when attempt.outcome in ('completed','failed') then attempt.outcome
      when attempt_failed then 'failed'
      else 'completed'
    end,
    -- The first terminal callback owns the finish timestamp. A late usage
    -- callback is a settlement update and must be idempotent.
    finished_at=coalesce(attempt.finished_at, finish_debate_provider_attempt.finished_at),
    usage_status=case
      when reported and attempt.usage_status='unknown' then 'reported'
      else attempt.usage_status
    end,
    prompt_tokens=case
      when reported and attempt.usage_status='unknown' then reported_prompt_tokens
      else attempt.prompt_tokens
    end,
    completion_tokens=case
      when reported and attempt.usage_status='unknown' then reported_completion_tokens
      else attempt.completion_tokens
    end,
    total_tokens=case
      when reported and attempt.usage_status='unknown' then reported_total_tokens
      else attempt.total_tokens
    end
    where attempt.id=requested_attempt_id
      and attempt.outcome in ('dispatched','completed','failed')
      and finish_debate_provider_attempt.finished_at >= attempt.dispatched_at
    returning to_jsonb(attempt.*) into result;
  if result is null then
    raise exception using errcode='PT409', message='Provider attempt is not finishable';
  end if;
  return result;
end; $$;

revoke all on function public.admit_debate_provider_attempt(jsonb,jsonb)
  from public,anon,authenticated;
revoke all on function public.dispatch_debate_provider_attempt(uuid,timestamptz)
  from public,anon,authenticated;
revoke all on function public.finish_debate_provider_attempt(uuid,timestamptz,bigint,bigint,bigint,boolean)
  from public,anon,authenticated;
grant execute on function public.admit_debate_provider_attempt(jsonb,jsonb) to service_role;
grant execute on function public.dispatch_debate_provider_attempt(uuid,timestamptz) to service_role;
grant execute on function public.finish_debate_provider_attempt(uuid,timestamptz,bigint,bigint,bigint,boolean)
  to service_role;
