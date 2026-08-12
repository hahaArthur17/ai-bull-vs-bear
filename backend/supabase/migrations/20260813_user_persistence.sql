-- Seed the supported MVP stocks and allow authenticated users to persist the
-- child records belonging to their own analysis runs.

insert into public.stocks (ticker, company_name, exchange, sector)
values
  ('AAPL', 'Apple Inc.', 'NASDAQ', 'Technology'),
  ('GOOG', 'Alphabet Inc.', 'NASDAQ', 'Communication Services'),
  ('NVDA', 'NVIDIA Corporation', 'NASDAQ', 'Technology'),
  ('TSLA', 'Tesla, Inc.', 'NASDAQ', 'Consumer Discretionary')
on conflict (ticker) do update set
  company_name = excluded.company_name,
  exchange = excluded.exchange,
  sector = excluded.sector;

grant insert on table
  public.agent_outputs,
  public.claim_evidence,
  public.token_usage
to authenticated;

grant usage, select on sequence
  public.agent_outputs_id_seq,
  public.token_usage_id_seq
to authenticated;

alter table public.claim_evidence enable row level security;

drop policy if exists "Users can create outputs for their analysis runs"
  on public.agent_outputs;
create policy "Users can create outputs for their analysis runs"
  on public.agent_outputs for insert
  with check (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = agent_outputs.analysis_run_id
        and analysis_runs.user_id = auth.uid()
    )
  );

drop policy if exists "Users can create token usage for their analysis runs"
  on public.token_usage;
create policy "Users can create token usage for their analysis runs"
  on public.token_usage for insert
  with check (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = token_usage.analysis_run_id
        and analysis_runs.user_id = auth.uid()
    )
  );

drop policy if exists "Users can read evidence links for their analysis runs"
  on public.claim_evidence;
create policy "Users can read evidence links for their analysis runs"
  on public.claim_evidence for select
  using (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = claim_evidence.analysis_run_id
        and analysis_runs.user_id = auth.uid()
    )
  );

drop policy if exists "Users can create evidence links for their analysis runs"
  on public.claim_evidence;
create policy "Users can create evidence links for their analysis runs"
  on public.claim_evidence for insert
  with check (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = claim_evidence.analysis_run_id
        and analysis_runs.user_id = auth.uid()
    )
  );
