-- Provider admission, Stop ordering, usage settlement, and privilege checks.
-- This deliberately runs against the reviewable fragment, not a hosted DB.
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
  '2026-09-10 00:00:00+00','2026-09-10 00:00:00+00'
);
insert into public.debate_jobs(
  id,session_id,user_id,job_type,status,idempotency_key,attempt_count,max_attempts,
  available_at,started_at,provider_request_count,prompt_tokens,completion_tokens,total_tokens,
  created_at,updated_at
) values (
  '40000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001','round_1','running','provider-sql-job',1,3,
  '2026-09-10 00:00:00+00','2026-09-10 00:00:01+00',1,100,25,125,
  '2026-09-10 00:00:00+00','2026-09-10 00:00:01+00'
);

set role service_role;

-- Admission creates one audit identity and one empty draft checkpoint.
select public.admit_debate_provider_attempt(
  jsonb_build_object(
    'id','60000000-0000-0000-0000-000000000001',
    'session_id','10000000-0000-0000-0000-000000000001',
    'generation_id','30000000-0000-0000-0000-000000000001',
    'message_id','50000000-0000-0000-0000-000000000001',
    'role','bull','provider','test-provider','model','test-model',
    'admitted_at','2026-09-10 00:00:02+00',
    'dispatched_at',null,'finished_at',null,'outcome','admitted',
    'usage_status','unknown','prompt_tokens',null,'completion_tokens',null,'total_tokens',null
  ),
  jsonb_build_object(
    'message_id','50000000-0000-0000-0000-000000000001',
    'session_id','10000000-0000-0000-0000-000000000001',
    'branch_id','20000000-0000-0000-0000-000000000001',
    'generation_id','30000000-0000-0000-0000-000000000001',
    'sequence_number',1,'round_number',1,'exchange_number',1,
    'role','bull','message_kind','argument','content','',
    'created_at','2026-09-10 00:00:02+00'
  )
);

do $$
declare checkpoint jsonb; attempt_count integer;
begin
  select payload into checkpoint from public.debate_draft_checkpoints
    where message_id='50000000-0000-0000-0000-000000000001';
  select count(*) into attempt_count from public.debate_provider_attempts
    where session_id='10000000-0000-0000-0000-000000000001';
  if attempt_count<>1 or checkpoint->>'content'<>''
     or checkpoint->>'is_complete'<>'false'
     or checkpoint->'metadata'<>'{}'::jsonb then
    raise exception 'admission did not seed one empty checkpoint and ledger row';
  end if;
end $$;

-- Exact retry is idempotent. Reusing the id for another model is rejected.
select public.admit_debate_provider_attempt(
  jsonb_build_object(
    'id','60000000-0000-0000-0000-000000000001',
    'session_id','10000000-0000-0000-0000-000000000001',
    'generation_id','30000000-0000-0000-0000-000000000001',
    'message_id','50000000-0000-0000-0000-000000000001',
    'role','bull','provider','test-provider','model','test-model',
    'admitted_at','2026-09-10 00:00:02+00',
    'dispatched_at',null,'finished_at',null,'outcome','admitted',
    'usage_status','unknown','prompt_tokens',null,'completion_tokens',null,'total_tokens',null
  ),
  jsonb_build_object(
    'message_id','50000000-0000-0000-0000-000000000001',
    'session_id','10000000-0000-0000-0000-000000000001',
    'branch_id','20000000-0000-0000-0000-000000000001',
    'generation_id','30000000-0000-0000-0000-000000000001',
    'sequence_number',1,'round_number',1,'exchange_number',1,
    'role','bull','message_kind','argument','content','',
    'created_at','2026-09-10 00:00:02+00'
  )
);
do $$
begin
  begin
    perform public.admit_debate_provider_attempt(
      jsonb_build_object(
        'id','60000000-0000-0000-0000-000000000001',
        'session_id','10000000-0000-0000-0000-000000000001',
        'generation_id','30000000-0000-0000-0000-000000000001',
        'message_id','50000000-0000-0000-0000-000000000001',
        'role','bull','provider','test-provider','model','changed-model',
        'admitted_at','2026-09-10 00:00:02+00','dispatched_at',null,'finished_at',null,
        'outcome','admitted','usage_status','unknown',
        'prompt_tokens',null,'completion_tokens',null,'total_tokens',null
      ),
      jsonb_build_object(
        'message_id','50000000-0000-0000-0000-000000000001',
        'session_id','10000000-0000-0000-0000-000000000001',
        'branch_id','20000000-0000-0000-0000-000000000001',
        'generation_id','30000000-0000-0000-0000-000000000001','sequence_number',1,
        'round_number',1,'exchange_number',1,'role','bull','message_kind','argument','content',''
      )
    );
    raise exception 'conflicting duplicate attempt was accepted';
  exception when sqlstate 'PT409' then null;
  end;
end $$;

-- Admission must agree with the session's running round and status.
do $$
declare attempt jsonb; checkpoint jsonb;
begin
  attempt := jsonb_build_object(
    'id','60000000-0000-0000-0000-000000000003',
    'session_id','10000000-0000-0000-0000-000000000001',
    'generation_id','30000000-0000-0000-0000-000000000001',
    'message_id','50000000-0000-0000-0000-000000000003',
    'role','bull','provider','test-provider','model','test-model',
    'admitted_at','2026-09-10 00:00:02+00','dispatched_at',null,'finished_at',null,
    'outcome','admitted','usage_status','unknown',
    'prompt_tokens',null,'completion_tokens',null,'total_tokens',null
  );
  checkpoint := jsonb_build_object(
    'message_id','50000000-0000-0000-0000-000000000003',
    'session_id','10000000-0000-0000-0000-000000000001',
    'branch_id','20000000-0000-0000-0000-000000000001',
    'generation_id','30000000-0000-0000-0000-000000000001',
    'sequence_number',2,'round_number',2,'exchange_number',1,
    'role','bull','message_kind','argument','content',''
  );
  begin
    perform public.admit_debate_provider_attempt(attempt,checkpoint);
    raise exception 'round-mismatched checkpoint was accepted';
  exception when sqlstate 'PT409' then null;
  end;

  update public.debate_sessions set status='awaiting_user'
    where id='10000000-0000-0000-0000-000000000001';
  checkpoint := jsonb_set(checkpoint,'{round_number}','1'::jsonb);
  begin
    perform public.admit_debate_provider_attempt(attempt,checkpoint);
    raise exception 'non-running session admission was accepted';
  exception when sqlstate 'PT409' then null;
  end;
  update public.debate_sessions set status='running_round_1'
    where id='10000000-0000-0000-0000-000000000001';
end $$;

select public.dispatch_debate_provider_attempt(
  '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:03+00'
);
-- An ambiguous transport retry with the exact timestamp returns the stored
-- dispatch. A different dispatch identity still conflicts.
select public.dispatch_debate_provider_attempt(
  '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:03+00'
);
do $$
begin
  begin
    perform public.dispatch_debate_provider_attempt(
      '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:04+00'
    );
    raise exception 'changed dispatch retry was accepted';
  exception when sqlstate 'PT409' then null;
  end;
end $$;
do $$
declare
  stored public.debate_provider_attempts%rowtype;
  replayed jsonb;
begin
  select * into strict stored from public.debate_provider_attempts
    where id='60000000-0000-0000-0000-000000000001';
  replayed := public.admit_debate_provider_attempt(
    to_jsonb(stored) || jsonb_build_object(
      'outcome','admitted','usage_status','unknown','dispatched_at',null,
      'finished_at',null,'prompt_tokens',null,'completion_tokens',null,'total_tokens',null
    ),
    jsonb_build_object(
      'message_id',stored.message_id,'session_id',stored.session_id,
      'branch_id','20000000-0000-0000-0000-000000000001',
      'generation_id',stored.generation_id,'sequence_number',1,
      'round_number',1,'exchange_number',1,'role',stored.role,
      'message_kind','argument','content',''
    )
  );
  if replayed->>'outcome' <> 'dispatched' then
    raise exception 'admission retry rewrote the dispatched lifecycle: %', replayed;
  end if;
end $$;
select public.finish_debate_provider_attempt(
  '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:04+00',null,null,null,true
);

-- A failed request has unknown usage until a complete late report arrives;
-- absent/partial usage never becomes synthetic zeroes.
select public.finish_debate_provider_attempt(
  '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:05+00',7,null,null,false
);
do $$
declare a public.debate_provider_attempts%rowtype;
begin
  select * into strict a from public.debate_provider_attempts
    where id='60000000-0000-0000-0000-000000000001';
  if a.outcome<>'failed' or a.usage_status<>'unknown'
     or a.prompt_tokens is not null or a.completion_tokens is not null or a.total_tokens is not null then
    raise exception 'unknown usage was converted to values or terminal outcome changed: %',to_jsonb(a);
  end if;
end $$;

-- Create canonical output and a later message, then Stop removes the
-- canonical suffix while retaining both provider and legacy job audit rows.
insert into public.debate_messages(
  id,session_id,branch_id,generation_id,sequence_number,round_number,exchange_number,
  role,message_kind,content,metadata,is_complete,created_at
) values (
  '50000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',1,1,1,'bull','argument','visible prefix canonical output','{}',true,
  '2026-09-10 00:00:04+00'
),(
  '50000000-0000-0000-0000-000000000002',
  '10000000-0000-0000-0000-000000000001','20000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',2,1,1,'bear','rebuttal','later output','{}',true,
  '2026-09-10 00:00:04+00'
);
select public.interrupt_debate_generation(
  '10000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '50000000-0000-0000-0000-000000000001',
  'visible prefix','2026-09-10 00:00:06+00'
);
select public.finish_debate_provider_attempt(
  '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:07+00',7,3,10,false
);
select public.finish_debate_provider_attempt(
  '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:08+00',7,3,10,true
);
select public.finish_debate_provider_attempt(
  '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:09+00',8,2,10,true
);
select public.finish_debate_provider_attempt(
  '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:10+00',8,2,11,true
);

do $$
declare a public.debate_provider_attempts%rowtype; j public.debate_jobs%rowtype; m public.debate_messages%rowtype;
begin
  select * into strict a from public.debate_provider_attempts
    where id='60000000-0000-0000-0000-000000000001';
  select * into strict j from public.debate_jobs
    where id='40000000-0000-0000-0000-000000000001';
  select * into strict m from public.debate_messages
    where id='50000000-0000-0000-0000-000000000001';
  if a.outcome<>'failed' or a.usage_status<>'reported'
     or (a.prompt_tokens,a.completion_tokens,a.total_tokens)<>(7,3,10) then
    raise exception 'late usage did not preserve failed attempt and report usage: %',to_jsonb(a);
  end if;
  if a.finished_at <> '2026-09-10 00:00:04+00' then
    raise exception 'repeated late usage changed terminal timestamp: %',to_jsonb(a);
  end if;
  if m.content<>'visible prefix' or m.is_complete
     or exists(select 1 from public.debate_messages where id='50000000-0000-0000-0000-000000000002') then
    raise exception 'Stop did not remove canonical suffix';
  end if;
  if j.status<>'running' or j.prompt_tokens<>100 or j.completion_tokens<>25 or j.total_tokens<>125 then
    raise exception 'legacy job audit changed during Stop: %',to_jsonb(j);
  end if;
end $$;

-- A retry reuses the same canonical turn sequence, so an old partial draft
-- must be removed when the Job returns to queued. The provider attempt row
-- remains available for settlement and audit.
insert into public.debate_draft_checkpoints(message_id,session_id,payload)
values (
  '50000000-0000-0000-0000-000000000099',
  '10000000-0000-0000-0000-000000000001',
  jsonb_build_object('id','50000000-0000-0000-0000-000000000099',
    'session_id','10000000-0000-0000-0000-000000000001',
    'generation_id','30000000-0000-0000-0000-000000000009',
    'branch_id','20000000-0000-0000-0000-000000000001',
    'sequence_number',2,'round_number',1,'exchange_number',1,
    'role','bear','message_kind','rebuttal','content','stale partial output')
);
update public.debate_jobs
  set status='queued', started_at=null, updated_at='2026-09-10 00:00:11+00'
  where id='40000000-0000-0000-0000-000000000001';
do $$
begin
  if exists (
    select 1 from public.debate_draft_checkpoints
      where session_id='10000000-0000-0000-0000-000000000001'
  ) then
    raise exception 'retry retained a stale draft checkpoint';
  end if;
end $$;

-- The old generation is stale after Stop, so no new provider attempt can be
-- admitted into the interrupted session.
do $$
begin
  begin
    perform public.admit_debate_provider_attempt(
      jsonb_build_object(
        'id','60000000-0000-0000-0000-000000000002',
        'session_id','10000000-0000-0000-0000-000000000001',
        'generation_id','30000000-0000-0000-0000-000000000001',
        'message_id','50000000-0000-0000-0000-000000000003',
        'role','bear','provider','test-provider','model','test-model',
        'admitted_at','2026-09-10 00:00:08+00','dispatched_at',null,'finished_at',null,
        'outcome','admitted','usage_status','unknown',
        'prompt_tokens',null,'completion_tokens',null,'total_tokens',null
      ),
      jsonb_build_object(
        'message_id','50000000-0000-0000-0000-000000000003',
        'session_id','10000000-0000-0000-0000-000000000001',
        'branch_id','20000000-0000-0000-0000-000000000001',
        'generation_id','30000000-0000-0000-0000-000000000001','sequence_number',2,
        'round_number',1,'exchange_number',1,'role','bear','message_kind','rebuttal','content',''
      )
    );
    raise exception 'stale generation admission was accepted';
  exception when sqlstate 'PT409' then null;
  end;
end $$;

reset role;

-- Provider rows and RPCs are service-only, including for the owner.
set local role authenticated;
do $$
begin
  begin
    perform count(*) from public.debate_provider_attempts;
    raise exception 'authenticated role can read provider attempt ledger';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.dispatch_debate_provider_attempt(
      '60000000-0000-0000-0000-000000000001','2026-09-10 00:00:08+00'
    );
    raise exception 'authenticated role can execute provider RPC';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;

rollback;
select 'debate provider attempt SQL checks passed' as result;
