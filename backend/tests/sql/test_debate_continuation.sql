-- SQL transaction semantics use a deliberately small Queue double. This does
-- not certify the hosted pgmq extension or PostgREST transport.
begin;
create schema if not exists pgmq;
create table pgmq.test_messages(id bigint generated always as identity primary key, payload jsonb);
create function pgmq.send(text,jsonb,integer) returns bigint language plpgsql as $$
declare result bigint;
begin
  if current_setting('test.fail_queue',true)='true' then raise exception 'injected Queue failure'; end if;
  insert into pgmq.test_messages(payload) values($2) returning id into result;
  return result;
end; $$;
grant usage on schema pgmq to service_role;
grant all on pgmq.test_messages to service_role;
grant usage on sequence pgmq.test_messages_id_seq to service_role;
insert into auth.users(id) values ('00000000-0000-0000-0000-000000000001');
insert into public.stocks(id) values (1);
insert into public.debate_sessions(id,user_id,stock_id,ticker,mode,status,opening_side,
  active_branch_id,active_generation_id,analysis_context,factor_snapshot,created_at,updated_at)
values ('10000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000001',
  1,'TEST','demo','interrupted_awaiting_user','bull','20000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001','{}','{}','2026-09-10 00:00:00Z','2026-09-10 00:00:00Z');
insert into public.debate_messages(id,session_id,branch_id,generation_id,sequence_number,round_number,
  exchange_number,role,message_kind,content,is_complete,cancelled_at,metadata,created_at)
values ('50000000-0000-0000-0000-000000000001','10000000-0000-0000-0000-000000000001',
  '20000000-0000-0000-0000-000000000001','30000000-0000-0000-0000-000000000002',1,1,1,
  'bull','argument','visible prefix ',false,'2026-09-10 00:00:01Z','{"interrupted":true}','2026-09-10 00:00:00Z');
set role service_role;
do $$
declare s jsonb; point jsonb; job jsonb; envelope jsonb; queued jsonb; result jsonb;
  sid uuid := '10000000-0000-0000-0000-000000000001';
  gen uuid := '30000000-0000-0000-0000-000000000001';
  point_id uuid := '50000000-0000-0000-0000-000000000003';
begin
  select to_jsonb(x) into s from public.debate_sessions x where id=sid;
  point := jsonb_build_object('id',point_id,'session_id',sid,'branch_id',s->>'active_branch_id',
    'generation_id',gen,'sequence_number',2,'round_number',1,'exchange_number',0,'role','user',
    'message_kind','question','content','What about risk?','terms','[]'::jsonb,'is_complete',true,
    'metadata',jsonb_build_object('interjection',true,'interrupted_message_id','50000000-0000-0000-0000-000000000001'),
    'created_at','2026-09-10 00:00:02Z');
  perform public.record_debate_interjection(point);
  perform public.record_debate_interjection(point);
  if (select count(*) from public.debate_jobs)<>0 or (select count(*) from pgmq.test_messages)<>0 then
    raise exception 'saving interjection dispatched work';
  end if;
  if (select count(*) from public.debate_messages)<>2 then raise exception 'interjection repeated'; end if;
  begin
    perform public.record_debate_interjection(point||'{"content":"changed"}'::jsonb);
    raise exception 'conflicting interjection accepted';
  exception when serialization_failure then null; end;
  queued := s||jsonb_build_object('status','queued_round_1','updated_at','2026-09-10 00:00:03Z',
    'active_generation_id','30000000-0000-0000-0000-000000000003');
  job := jsonb_build_object('id','40000000-0000-0000-0000-000000000001','session_id',sid,
    'user_id',s->>'user_id','job_type','round_1','status','queued','idempotency_key','continue:'||sid::text||':'||gen::text||':'||point_id::text||':continue-sql-key',
    'attempt_count',0,'max_attempts',3,'provider_request_count',0,'prompt_tokens',0,'completion_tokens',0,'total_tokens',0,
    'available_at','2026-09-10 00:00:03Z','created_at','2026-09-10 00:00:03Z','updated_at','2026-09-10 00:00:03Z');
  envelope := jsonb_build_object('job_id',job->>'id','session_id',sid,'job_type','round_1');
  perform set_config('test.fail_queue','true',true);
  begin
    perform public.continue_interrupted_debate(queued,job,envelope,gen,point_id);
    raise exception 'Queue failure was ignored';
  exception when raise_exception then
    if sqlerrm<>'injected Queue failure' then raise; end if;
  end;
  if (select status from public.debate_sessions where id=sid)<>'interrupted_awaiting_user'
    or (select count(*) from public.debate_jobs)<>0 then raise exception 'Queue failure left partial transaction'; end if;
  perform set_config('test.fail_queue','false',true);
  begin
    perform public.continue_interrupted_debate(queued||'{"analysis_context":{"changed":true}}'::jsonb,job,envelope,gen,point_id);
    raise exception 'changed snapshot was accepted';
  exception when serialization_failure then null; end;
  result := public.continue_interrupted_debate(queued,job,envelope,gen,point_id);
  if result#>>'{session,status}'<>'queued_round_1' or result#>>'{job,queue_message_id}' is null then
    raise exception 'Continue failed'; end if;
  perform public.continue_interrupted_debate(queued,job,envelope,gen,point_id);
  begin
    perform public.continue_interrupted_debate(queued,job,envelope,gen,'50000000-0000-0000-0000-000000000099');
    raise exception 'Continue replay with changed point accepted';
  exception when serialization_failure then null; end;
  if (select count(*) from pgmq.test_messages)<>1 or (select count(*) from public.debate_jobs)<>1 then
    raise exception 'Continue duplicated Queue or job'; end if;
  begin
    perform public.continue_interrupted_debate(queued,job||'{"id":"40000000-0000-0000-0000-000000000002"}'::jsonb,envelope,gen,point_id);
    raise exception 'second Continue accepted';
  exception when serialization_failure then null; end;
end $$;
reset role;
rollback;
select 'interjection and atomic continuation SQL checks passed' as result;
