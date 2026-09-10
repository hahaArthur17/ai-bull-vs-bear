-- Before-first-output Stop is a durable empty anchor and an atomic queue
-- cancellation. This runs against the canonical migration in a local DB.
begin;

insert into auth.users(id) values ('00000000-0000-0000-0000-000000000001');
insert into public.stocks(id) values (1);
insert into public.debate_sessions(
  id,user_id,stock_id,ticker,mode,status,opening_side,active_branch_id,
  active_generation_id,analysis_context,factor_snapshot,guardrail_status,
  created_at,updated_at
) values (
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',1,'TEST','demo','queued_round_1','bull',
  '20000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001','{}','{}','passed',
  '2026-09-10 00:00:00+00','2026-09-10 00:00:00+00'
);
insert into public.debate_jobs(
  id,session_id,user_id,job_type,status,idempotency_key,available_at,
  created_at,updated_at
) values (
  '40000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001','round_1','queued',
  'before-output-job','2026-09-10 00:00:00+00',
  '2026-09-10 00:00:00+00','2026-09-10 00:00:00+00'
);

set role service_role;
select public.interrupt_debate_before_output_generation(
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '2026-09-10 00:00:01+00'
);

do $$
declare
  session_row public.debate_sessions%rowtype;
  anchor public.debate_messages%rowtype;
  job_row public.debate_jobs%rowtype;
begin
  select * into strict session_row from public.debate_sessions
    where id='10000000-0000-0000-0000-000000000001';
  if session_row.status <> 'interrupted_awaiting_user'
     or session_row.active_generation_id='30000000-0000-0000-0000-000000000001' then
    raise exception 'before-output Stop did not rotate the waiting generation: %', to_jsonb(session_row);
  end if;
  select * into strict anchor from public.debate_messages
    where id='30000000-0000-0000-0000-000000000001';
  if anchor.content <> '' or anchor.is_complete
     or anchor.cancelled_at <> '2026-09-10 00:00:01+00'
     or anchor.metadata <> '{"interrupted":true,"before_output":true}'::jsonb then
    raise exception 'before-output anchor is not empty and cancelled: %', to_jsonb(anchor);
  end if;
  select * into strict job_row from public.debate_jobs
    where id='40000000-0000-0000-0000-000000000001';
  if job_row.status <> 'cancelled' or job_row.finished_at <> '2026-09-10 00:00:01+00' then
    raise exception 'queued job was not cancelled with the anchor: %', to_jsonb(job_row);
  end if;
end $$;

-- Retrying with the original generation is idempotent and cannot add a second
-- empty anchor.
select public.interrupt_debate_before_output_generation(
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '2026-09-10 00:00:02+00'
);
do $$
begin
  if (select count(*) from public.debate_messages) <> 1 then
    raise exception 'before-output retry created another anchor';
  end if;
end $$;
reset role;

rollback;
select 'before-output interruption SQL checks passed' as result;
