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
     or (message_payload ->> 'round_number')::integer is distinct from
        case when s.status='running_round_1' then 1 else 2 end then
    raise exception using errcode='40001', message='Draft generation is not active';
  end if;
  select payload into previous from public.debate_draft_checkpoints where message_id=mid;
  if previous is not null and (
    previous ->> 'session_id' is distinct from message_payload ->> 'session_id'
    or previous ->> 'generation_id' is distinct from message_payload ->> 'generation_id'
    or previous ->> 'branch_id' is distinct from message_payload ->> 'branch_id'
    or previous ->> 'sequence_number' is distinct from message_payload ->> 'sequence_number'
    or left(message_payload ->> 'content', char_length(previous ->> 'content'))
       is distinct from previous ->> 'content') then
    raise exception using errcode='40001', message='Draft prefix changed';
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
    raise exception using errcode='40001', message='Interruption target unavailable';
  end if;
  select to_jsonb(m) into target from public.debate_messages m where id=requested_message_id;
  if target is null then
    select payload into target from public.debate_draft_checkpoints where message_id=requested_message_id;
  end if;
  if target is null or (target ->> 'session_id')::uuid is distinct from s.id
      or (target ->> 'branch_id')::uuid is distinct from s.active_branch_id then
    raise exception using errcode='40001', message='Interruption target unavailable';
  end if;
  if s.status='cancelled' and target ->> 'is_complete'='false'
      and target #>> '{metadata,interrupted}'='true'
      and (target ->> 'generation_id')::uuid=requested_generation_id
      and target ->> 'content'=visible_prefix then
    return to_jsonb(s);
  end if;
  if s.status in ('cancelled','cancel_requested','failed')
      or s.active_generation_id is distinct from requested_generation_id
      or (target ->> 'generation_id')::uuid is distinct from requested_generation_id
      or target ->> 'role' not in ('bull','bear','judge')
      or visible_prefix is null or char_length(visible_prefix)>6000
      or left(target ->> 'content',char_length(visible_prefix)) is distinct from visible_prefix then
    raise exception using errcode='40001', message='Interruption prefix or generation is invalid';
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
  update public.debate_sessions set status='cancelled',active_generation_id=gen_random_uuid(),
    updated_at=interrupted_at,completed_at=interrupted_at,final_judge_message_id=null,
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
  elsif new.status in ('completed','cancelled','failed') then
    delete from public.debate_draft_checkpoints where session_id=new.id;
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
