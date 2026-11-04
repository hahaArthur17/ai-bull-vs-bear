-- Each assertion runs against the checked-in grants and policies. Roll back
-- fixture records so the same checks can run after migration replay as well.
begin;
insert into auth.users(id) values
  ('00000000-0000-4000-8000-000000000001'),
  ('00000000-0000-4000-8000-000000000002');
insert into public.stocks(id,ticker,company_name,exchange)
  values (100,'TEST','Permission fixture','TEST');
insert into public.analysis_runs(id,user_id,stock_id) values
  ('10000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000001',100),
  ('10000000-0000-4000-8000-000000000002','00000000-0000-4000-8000-000000000002',100);
insert into public.agent_outputs(analysis_run_id,agent_name,output_json) values
  ('10000000-0000-4000-8000-000000000001','bull','{}'),
  ('10000000-0000-4000-8000-000000000002','bear','{}');

do $$
declare table_name text;
begin
  for table_name in select tablename from pg_tables where schemaname='public' loop
    assert (select relrowsecurity from pg_class where oid=('public.'||table_name)::regclass),
      'Every exposed table must enable RLS';
    assert not has_table_privilege('anon','public.'||table_name,'INSERT,UPDATE,DELETE,TRUNCATE'),
      'Anonymous roles must never mutate base tables';
    assert not has_table_privilege('authenticated','public.'||table_name,'TRUNCATE'),
      'TRUNCATE bypasses RLS and must be revoked';
  end loop;
end $$;

set local role anon;
do $$
begin
  assert (select count(*) from public.stocks where ticker='TEST') = 1,
    'Anonymous catalog reads must remain available';
  begin
    perform 1 from public.analysis_runs;
    raise exception 'Anonymous private read succeeded';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into public.stocks(ticker,company_name,exchange) values ('BAD','Bad','BAD');
    raise exception 'Anonymous market write succeeded';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;

set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true);
do $$
begin
  assert (select count(*) from public.analysis_runs) = 1, 'Cross-user analysis read';
  assert (select count(*) from public.agent_outputs) = 1, 'Cross-user child read';
  insert into public.watchlists(user_id,stock_id)
    values ('00000000-0000-4000-8000-000000000001',100);
  assert (select count(*) from public.watchlists) = 1, 'Owner watchlist insert failed';
  insert into public.agent_outputs(analysis_run_id,agent_name,output_json)
    values ('10000000-0000-4000-8000-000000000001','judge','{}');
  begin
    insert into public.watchlists(user_id,stock_id)
      values ('00000000-0000-4000-8000-000000000002',100);
    raise exception 'Cross-user watchlist insert succeeded';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into public.agent_outputs(analysis_run_id,agent_name,output_json)
      values ('10000000-0000-4000-8000-000000000002','judge','{}');
    raise exception 'Cross-user child insert succeeded';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into public.analysis_runs(user_id,stock_id)
      values ('00000000-0000-4000-8000-000000000002',100);
    raise exception 'Cross-user parent insert succeeded';
  exception when insufficient_privilege then null;
  end;
  begin
    update public.stocks set company_name='tampered' where id=100;
    raise exception 'Authenticated market write succeeded';
  exception when insufficient_privilege then null;
  end;
end $$;

select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000002',true);
do $$
begin
  assert (select count(*) from public.watchlists) = 0, 'Cross-user watchlist read';
  delete from public.watchlists;
end $$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true);
do $$
begin
  assert (select count(*) from public.watchlists) = 1, 'Cross-user watchlist delete';
  delete from public.watchlists;
  assert (select count(*) from public.watchlists) = 0, 'Owner watchlist delete failed';
end $$;
reset role;
rollback;
