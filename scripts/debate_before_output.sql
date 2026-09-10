-- This SQL is retained as a reviewable replay fragment. The same definitions
-- are included in the canonical 20260909_debate_draft_interruption migration;
-- deployments apply that migration and do not need this file separately.

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
    raise exception using errcode='40001', message='Before-output interruption target unavailable';
  end if;

  -- The generation UUID is also the stable empty anchor id. A retry after the
  -- generation rotation finds this row and returns the same stopped session.
  select * into existing_message from public.debate_messages where id=requested_generation_id;
  if found then
    if existing_message.session_id <> s.id then
      raise exception using errcode='40001', message='Before-output anchor identifier collision';
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
    raise exception using errcode='40001', message='Before-output anchor identifier already exists';
  end if;

  select * into existing_draft from public.debate_draft_checkpoints
    where message_id=requested_generation_id;
  if found and (existing_draft.session_id <> s.id
                or (existing_draft.payload->>'generation_id')::uuid is distinct from requested_generation_id) then
    raise exception using errcode='40001', message='Before-output anchor identifier collision';
  end if;

  if s.status not in ('queued_round_1','queued_round_2','running_round_1','running_round_2')
     or s.active_generation_id is distinct from requested_generation_id then
    raise exception using errcode='40001', message='Debate generation is not waiting before output';
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
    raise exception using errcode='40001', message='Debate generation has already produced output';
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
