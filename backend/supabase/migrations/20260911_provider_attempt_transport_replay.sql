-- A provider admission can commit even when the caller times out before
-- receiving its response. Admission is already exactly replayable. Make the
-- following dispatch boundary exactly replayable as well so the application
-- can retry one ambiguous transport failure without dispatching a model twice.
create or replace function public.dispatch_debate_provider_attempt(
  requested_attempt_id uuid, dispatched_at timestamptz
) returns jsonb language plpgsql set search_path='' as $$
declare result jsonb; existing public.debate_provider_attempts%rowtype;
begin
  update public.debate_provider_attempts as attempt set
    outcome='dispatched', dispatched_at=dispatch_debate_provider_attempt.dispatched_at
    where attempt.id=requested_attempt_id and attempt.outcome='admitted'
      and dispatch_debate_provider_attempt.dispatched_at >= attempt.admitted_at
    returning to_jsonb(attempt.*) into result;
  if result is not null then
    return result;
  end if;
  select * into existing from public.debate_provider_attempts
    where id=requested_attempt_id;
  if found
     and existing.outcome in ('dispatched','completed','failed')
     and existing.dispatched_at=dispatch_debate_provider_attempt.dispatched_at then
    return to_jsonb(existing);
  end if;
  raise exception using errcode='PT409', message='Provider attempt is not dispatchable';
end; $$;

revoke all on function public.dispatch_debate_provider_attempt(uuid,timestamptz)
  from public,anon,authenticated;
grant execute on function public.dispatch_debate_provider_attempt(uuid,timestamptz)
  to service_role;
