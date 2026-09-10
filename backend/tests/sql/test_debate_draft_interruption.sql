begin;

insert into auth.users(id) values ('00000000-0000-0000-0000-000000000001');
insert into public.stocks(id) values (1);
insert into public.debate_sessions(
  id,user_id,stock_id,ticker,mode,status,opening_side,active_branch_id,
  active_generation_id,analysis_context,factor_snapshot,guardrail_status,
  created_at,updated_at
) values (
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',1,'TEST','demo','running_round_1','bull',
  '20000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001','{}','{}','passed',
  '2026-09-09 00:00:00+00','2026-09-09 00:00:00+00'
);
insert into public.debate_jobs(
  id,session_id,user_id,job_type,status,idempotency_key,attempt_count,max_attempts,
  available_at,started_at,provider_request_count,prompt_tokens,completion_tokens,total_tokens,
  created_at,updated_at
) values (
  '40000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001','round_1','running','interrupt-test-job',1,3,
  '2026-09-09 00:00:00+00','2026-09-09 00:00:01+00',2,100,25,125,
  '2026-09-09 00:00:00+00','2026-09-09 00:00:01+00'
);

set role service_role;
select public.checkpoint_debate_draft(jsonb_build_object(
  'id','50000000-0000-0000-0000-000000000001',
  'session_id','10000000-0000-0000-0000-000000000001',
  'branch_id','20000000-0000-0000-0000-000000000001',
  'generation_id','30000000-0000-0000-0000-000000000001',
  'sequence_number',1,'round_number',1,'exchange_number',1,
  'role','bull','message_kind','argument','content','Bull thesis continues',
  'metadata',jsonb_build_object('provider_cost_usd',0.42,'trace_id','kept-before-stop'),
  'is_complete',false,'cancelled_at','2026-09-09 00:00:02+00','created_at','2026-09-09 00:00:00+00'
));

do $$
begin
  begin
    perform public.checkpoint_debate_draft(jsonb_build_object(
      'id','50000000-0000-0000-0000-000000000001',
      'session_id','10000000-0000-0000-0000-000000000001',
      'branch_id','20000000-0000-0000-0000-000000000001',
      'generation_id','30000000-0000-0000-0000-000000000001',
      'sequence_number',1,'round_number',1,'role','bull','content','Changed'));
    raise exception 'changed prefix was accepted';
  exception when serialization_failure then null;
  end;
end $$;

select public.interrupt_debate_generation(
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  'Bull thesis','2026-09-09 00:00:03+00'
);
-- Idempotent retry with the original generation id must still succeed.
select public.interrupt_debate_generation(
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  'Bull thesis','2026-09-09 00:00:03+00'
);
reset role;

do $$
declare
  session_row public.debate_sessions%rowtype;
  message_row public.debate_messages%rowtype;
  job_row public.debate_jobs%rowtype;
begin
  select * into strict session_row from public.debate_sessions
    where id='10000000-0000-0000-0000-000000000001';
  if session_row.status <> 'interrupted_awaiting_user' or session_row.completed_at is not null
     or session_row.active_generation_id = '30000000-0000-0000-0000-000000000001' then
    raise exception 'session interruption state is incorrect: %', to_jsonb(session_row);
  end if;
  select * into strict message_row from public.debate_messages
    where id='50000000-0000-0000-0000-000000000001';
  if message_row.content <> 'Bull thesis' or message_row.is_complete
     or message_row.cancelled_at <> '2026-09-09 00:00:03+00' then
    raise exception 'visible prefix was not persisted correctly: %', to_jsonb(message_row);
  end if;
  if not (message_row.metadata ? 'provider_cost_usd') or not (message_row.metadata ? 'trace_id') then
    raise notice 'COST_METADATA_LOST: interrupt replaces existing message metadata: %', message_row.metadata;
  end if;
  if exists(select 1 from public.debate_draft_checkpoints) then
    raise exception 'checkpoint was not pruned';
  end if;
  select * into strict job_row from public.debate_jobs
    where id='40000000-0000-0000-0000-000000000001';
  if job_row.prompt_tokens <> 100 or job_row.completion_tokens <> 25 or job_row.total_tokens <> 125 then
    raise exception 'usage counters were changed: %', to_jsonb(job_row);
  end if;
  if job_row.status = 'running' then
    raise notice 'RUNNING_JOB_RETAINED: active job remains running after interruption';
  end if;
end $$;

-- Authenticated users can read their own canonical rows, but never drafts or RPCs.
set local role authenticated;
set local "request.jwt.claim.sub" = '00000000-0000-0000-0000-000000000001';
do $$
begin
  if (select count(*) from public.debate_sessions) <> 1 then
    raise exception 'owner RLS read failed';
  end if;
  begin
    perform count(*) from public.debate_draft_checkpoints;
    raise exception 'authenticated role could read draft checkpoints';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.checkpoint_debate_draft('{}');
    raise exception 'authenticated role could execute checkpoint RPC';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;

-- The checkpoint FK must cascade when its session is deleted.
insert into public.debate_sessions(
  id,user_id,stock_id,ticker,mode,status,opening_side,active_branch_id,
  active_generation_id,analysis_context,factor_snapshot,guardrail_status,created_at,updated_at
) values (
  '10000000-0000-0000-0000-000000000002','00000000-0000-0000-0000-000000000001',
  1,'TEST','demo','running_round_1','bull','20000000-0000-0000-0000-000000000002',
  '30000000-0000-0000-0000-000000000002','{}','{}','passed',now(),now()
);
insert into public.debate_draft_checkpoints(message_id,session_id,payload) values (
  '50000000-0000-0000-0000-000000000002','10000000-0000-0000-0000-000000000002',
  '{"content":"draft"}'
);
delete from public.debate_sessions where id='10000000-0000-0000-0000-000000000002';
do $$ begin
  if exists(select 1 from public.debate_draft_checkpoints
    where message_id='50000000-0000-0000-0000-000000000002') then
    raise exception 'checkpoint FK did not cascade';
  end if;
end $$;

rollback;
select 'debate interruption migration checks passed' as result;
