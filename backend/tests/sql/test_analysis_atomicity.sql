-- BB-001/BB-002: execute real transaction, retry and ownership assertions.
begin;
insert into auth.users(id) values
  ('00000000-0000-4000-8000-000000000001'),
  ('00000000-0000-4000-8000-000000000002');
insert into public.stocks(id,ticker,company_name,exchange)
  values (100,'TEST','Atomic analysis fixture','TEST');
insert into public.evidence_documents(id,stock_id,source_type,external_id,title,raw_text)
  values (200,100,'filing','doc-test','Test filing','Dated source material');
insert into public.evidence_chunks(id,document_id,chunk_text)
  values (300,200,'Dated source material');

create function pg_temp.analysis_payload(run_id text) returns jsonb language sql as $$
  select jsonb_build_object(
    'analysis_id',run_id,'ticker','TEST','question','Test',
    'created_at','2026-10-17T00:00:00Z','guardrail_status','passed',
    'bull',jsonb_build_object('id','bull-'||run_id,'evidence_ids',jsonb_build_array('chunk-300','doc-test')),
    'bear',jsonb_build_object('id','bear-'||run_id,'evidence_ids',jsonb_build_array('technical-test')),
    'judge',jsonb_build_object('summary','Uncertain','risk_level','medium'),
    'trace','[]'::jsonb,'token_usage',jsonb_build_object(
      'model_name','test','prompt_tokens',10,'completion_tokens',5,'total_tokens',15),
    'evidence',jsonb_build_array(
      jsonb_build_object('id','chunk-300','source_type','filing'),
      jsonb_build_object('id','doc-test','source_type','filing'),
      jsonb_build_object('id','technical-test','source_type','technical'))
  );
$$;

do $$ begin
  assert not has_function_privilege('anon','public.save_analysis_response(jsonb)','EXECUTE'),
    'Anonymous callers must not execute analysis writes';
  assert not (select prosecdef from pg_proc where oid='public.save_analysis_response(jsonb)'::regprocedure),
    'Analysis writes must preserve RLS';
end $$;
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true);
select public.save_analysis_response(pg_temp.analysis_payload('10000000-0000-4000-8000-000000000001'));
select public.save_analysis_response(pg_temp.analysis_payload('10000000-0000-4000-8000-000000000001'));
do $$
declare payload jsonb;
begin
  assert (select count(*) from public.analysis_runs)=1, 'Retries duplicated analysis';
  assert (select count(*) from public.agent_outputs)=5, 'Retries duplicated outputs';
  assert (select count(*) from public.token_usage)=1, 'Retries duplicated accounting';
  assert (select count(*) from public.claim_evidence where evidence_document_id=200)=1,
    'Chunk and external-ID citations must resolve and deduplicate by document';
  begin
    payload := pg_temp.analysis_payload('10000000-0000-4000-8000-000000000001');
    perform public.save_analysis_response(jsonb_set(payload,'{question}','"Changed"'));
    raise exception 'Retry silently replaced a different result';
  exception when sqlstate 'PT409' then null;
  end;
  -- Fail after the parent and output inserts: none may escape the RPC.
  begin
    payload := pg_temp.analysis_payload('10000000-0000-4000-8000-000000000002');
    perform public.save_analysis_response(jsonb_set(payload,'{token_usage,prompt_tokens}','"invalid"'));
    raise exception 'Invalid token accounting was accepted';
  exception when invalid_text_representation then null;
  end;
  -- Fail even later, during citation linking, after token accounting was written.
  begin
    payload := pg_temp.analysis_payload('10000000-0000-4000-8000-000000000003');
    perform public.save_analysis_response(jsonb_set(payload,'{bull,evidence_ids}','["missing-document"]'));
    raise exception 'Unresolved citation was silently dropped';
  exception when foreign_key_violation then null;
  end;
  assert (select count(*) from public.analysis_runs)=1, 'Failure left an orphan parent';
  assert (select count(*) from public.agent_outputs)=5, 'Failure left partial outputs';
  assert (select count(*) from public.token_usage)=1, 'Failure left partial accounting';
end $$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000002',true);
do $$ begin
  assert (select count(*) from public.agent_outputs)=0, 'Cross-user analysis read';
  begin
    perform public.save_analysis_response(pg_temp.analysis_payload('10000000-0000-4000-8000-000000000001'));
    raise exception 'Cross-user retry succeeded';
  exception when unique_violation then null;
  end;
end $$;
select set_config('request.jwt.claim.sub','',true);
do $$ begin
  begin
    perform public.save_analysis_response(pg_temp.analysis_payload('10000000-0000-4000-8000-000000000004'));
    raise exception 'Missing user identity was accepted';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;
rollback;
