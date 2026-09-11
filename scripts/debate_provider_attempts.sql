-- Reviewable replay fragment. The same definitions are included in the
-- canonical 20260909_debate_draft_interruption migration; deployments apply
-- that migration and do not need this file separately.
--
-- Provider attempts are the durable billing/audit identity for one provider
-- request. They intentionally do not reference debate_messages: Stop may
-- remove or replace canonical output while the provider callback still needs
-- to settle this row.
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
declare result jsonb; existing public.debate_provider_attempts%rowtype;
begin
  update public.debate_provider_attempts as attempt set
    outcome='dispatched', dispatched_at=dispatch_debate_provider_attempt.dispatched_at
    where attempt.id=requested_attempt_id and attempt.outcome='admitted'
      and dispatch_debate_provider_attempt.dispatched_at >= attempt.admitted_at
    returning to_jsonb(attempt.*) into result;
  if result is not null then
    return result;
  end if;
  select * into existing from public.debate_provider_attempts
    where id=requested_attempt_id;
  if found
     and existing.outcome in ('dispatched','completed','failed')
     and existing.dispatched_at=dispatch_debate_provider_attempt.dispatched_at then
    return to_jsonb(existing);
  end if;
  raise exception using errcode='PT409', message='Provider attempt is not dispatchable';
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
