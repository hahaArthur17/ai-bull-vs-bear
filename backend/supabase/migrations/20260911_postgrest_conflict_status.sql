-- PostgREST 14 retries SQLSTATE 40001 because it denotes a transient
-- serialization failure. Debate RPCs use durable optimistic conflicts, not
-- retryable database serialization failures, so return an explicit HTTP 409.
--
-- Fresh installations already receive PT409 from the corrected source
-- migrations. This idempotent migration updates projects that applied the
-- earlier definitions without duplicating all function bodies here.
do $migration$
declare
  function_oid oid;
  definition text;
begin
  for function_oid in
    select procedure.oid
    from pg_catalog.pg_proc as procedure
    join pg_catalog.pg_namespace as namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname = any(array[
        'append_debate_message',
        'checkpoint_debate_draft',
        'interrupt_debate_generation',
        'record_debate_interjection',
        'continue_interrupted_debate',
        'interrupt_debate_before_output_generation',
        'admit_debate_provider_attempt',
        'dispatch_debate_provider_attempt',
        'finish_debate_provider_attempt'
      ])
  loop
    definition := pg_catalog.pg_get_functiondef(function_oid);
    if pg_catalog.strpos(definition, '''40001''') > 0 then
      execute pg_catalog.replace(definition, '''40001''', '''PT409''');
    end if;
  end loop;

  if exists (
    select 1
    from pg_catalog.pg_proc as procedure
    join pg_catalog.pg_namespace as namespace
      on namespace.oid = procedure.pronamespace
    where namespace.nspname = 'public'
      and procedure.proname = any(array[
        'append_debate_message',
        'checkpoint_debate_draft',
        'interrupt_debate_generation',
        'record_debate_interjection',
        'continue_interrupted_debate',
        'interrupt_debate_before_output_generation',
        'admit_debate_provider_attempt',
        'dispatch_debate_provider_attempt',
        'finish_debate_provider_attempt'
      ])
      and pg_catalog.strpos(procedure.prosrc, '40001') > 0
  ) then
    raise exception 'A Debate RPC still exposes retryable SQLSTATE 40001';
  end if;
end;
$migration$;
