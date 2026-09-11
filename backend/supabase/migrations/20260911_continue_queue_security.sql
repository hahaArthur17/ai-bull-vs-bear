-- Continue is the only interruption RPC that writes directly to pgmq. The
-- existing Queue admission RPCs use the same tightly scoped SECURITY DEFINER
-- boundary because service_role does not receive direct pgmq schema access.
alter function public.continue_interrupted_debate(jsonb,jsonb,jsonb,uuid,uuid)
  security definer;

revoke all on function public.continue_interrupted_debate(jsonb,jsonb,jsonb,uuid,uuid)
  from public, anon, authenticated;
grant execute on function public.continue_interrupted_debate(jsonb,jsonb,jsonb,uuid,uuid)
  to service_role;
