-- BB-001/BB-002: one authenticated RPC owns the complete analysis write.
-- SECURITY INVOKER preserves table grants/RLS; the owner comes only from JWT.
create or replace function public.save_analysis_response(p_analysis jsonb)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
  owner_id uuid := auth.uid();
  run_id uuid := (p_analysis->>'analysis_id')::uuid;
  stock_record_id bigint;
  previous_response jsonb;
  claim jsonb;
  citation text;
  document_record_id bigint;
begin
  if owner_id is null then
    raise insufficient_privilege using message = 'Authentication required';
  end if;
  if run_id is null or jsonb_typeof(p_analysis->'evidence') <> 'array' then
    raise invalid_parameter_value using message = 'Invalid analysis payload';
  end if;
  -- Serialize retries for this ID. A lost HTTP response can be retried with
  -- exactly the same payload without duplicating children or token accounting.
  perform pg_advisory_xact_lock(hashtextextended(run_id::text, 0));
  select output_json into previous_response from public.agent_outputs
    where analysis_run_id = run_id and agent_name = 'response';
  if found then
    if previous_response = p_analysis then return; end if;
    raise sqlstate 'PT409' using message = 'Analysis ID already contains a different result';
  end if;
  select id into strict stock_record_id from public.stocks
    where ticker = upper(p_analysis->>'ticker');

  insert into public.analysis_runs
    (id, user_id, stock_id, question, final_summary, guardrail_status, risk_level, created_at)
  values
    (run_id, owner_id, stock_record_id, p_analysis->>'question',
     p_analysis->'judge'->>'summary', p_analysis->>'guardrail_status',
     p_analysis->'judge'->>'risk_level', (p_analysis->>'created_at')::timestamptz);
  insert into public.agent_outputs (analysis_run_id, agent_name, output_json)
    select run_id, entry.key, entry.value from jsonb_each(jsonb_build_object(
      'bull', p_analysis->'bull', 'bear', p_analysis->'bear',
      'judge', p_analysis->'judge', 'trace', p_analysis->'trace', 'response', p_analysis
    )) as entry;
  insert into public.token_usage
    (analysis_run_id, model_name, prompt_tokens, completion_tokens, total_tokens)
  values
    (run_id, p_analysis->'token_usage'->>'model_name',
     (p_analysis->'token_usage'->>'prompt_tokens')::integer,
     (p_analysis->'token_usage'->>'completion_tokens')::integer,
     (p_analysis->'token_usage'->>'total_tokens')::integer);

  for claim in select value from jsonb_array_elements(
    jsonb_build_array(p_analysis->'bull', p_analysis->'bear')
  ) loop
    for citation in select value from jsonb_array_elements_text(claim->'evidence_ids') loop
      if not exists (select 1 from jsonb_array_elements(p_analysis->'evidence') as item
                     where item->>'id' = citation) then
        raise foreign_key_violation using message = 'Citation is absent from the frozen evidence';
      end if;
      select doc.id into document_record_id from public.evidence_documents as doc
        where doc.stock_id = stock_record_id and (
          doc.external_id = citation or exists (
            select 1 from public.evidence_chunks as chunk
            where chunk.document_id = doc.id and 'chunk-' || chunk.id::text = citation
          )
        )
        order by doc.id limit 1;
      if not found then
        -- Generated technical observations live only in the frozen response.
        -- Stored technical documents, when present, still receive a real link.
        if exists (select 1 from jsonb_array_elements(p_analysis->'evidence') as item
                   where item->>'id' = citation and item->>'source_type' = 'technical'
                     and citation like 'technical-%') then
          continue;
        end if;
        raise foreign_key_violation using message = 'Analysis citation has no matching source document';
      end if;
      if not exists (select 1 from public.claim_evidence
                     where analysis_run_id = run_id and claim_id = claim->>'id'
                       and evidence_document_id = document_record_id) then
        insert into public.claim_evidence (claim_id, analysis_run_id, evidence_document_id)
          values (claim->>'id', run_id, document_record_id);
      end if;
    end loop;
  end loop;
end;
$$;

revoke all on function public.save_analysis_response(jsonb) from public, anon;
grant execute on function public.save_analysis_response(jsonb) to authenticated;

-- History reads use this order and batch-load the matching response rows.
create index if not exists analysis_runs_owner_recent_idx
  on public.analysis_runs (user_id, created_at desc, id desc);
create index if not exists agent_outputs_response_run_idx
  on public.agent_outputs (analysis_run_id) where agent_name = 'response';

create index if not exists agent_outputs_claim_lookup_idx
  on public.agent_outputs ((output_json->>'id')) where agent_name in ('bull','bear');

-- Make the new RPC visible immediately to PostgREST after deployment.
notify pgrst, 'reload schema';
