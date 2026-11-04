-- Align existing installations with the secure fresh-install schema.
-- No rows or data-model columns are changed.
begin;

-- Grants and RLS are both required: RLS cannot remove TRUNCATE privileges,
-- and hosted projects may have automatic default grants to API roles.
revoke all on table
  public.stocks,
  public.stock_prices,
  public.stock_price_history,
  public.technical_indicators,
  public.financial_facts,
  public.evidence_documents,
  public.evidence_chunks,
  public.macro_series,
  public.macro_observations,
  public.embedding_profiles,
  public.chunk_embeddings,
  public.watchlists,
  public.analysis_runs,
  public.agent_outputs,
  public.claim_evidence,
  public.token_usage
from public, anon, authenticated;

revoke all on sequence public.agent_outputs_id_seq, public.token_usage_id_seq
from public, anon, authenticated;

grant usage on schema public to anon, authenticated, service_role;
grant all privileges on all tables in schema public to service_role;
grant all privileges on all sequences in schema public to service_role;
alter default privileges in schema public grant all privileges on tables to service_role;
alter default privileges in schema public grant all privileges on sequences to service_role;

grant select on table
  public.stocks,
  public.stock_prices,
  public.stock_price_history,
  public.technical_indicators,
  public.financial_facts,
  public.evidence_documents,
  public.evidence_chunks,
  public.macro_series,
  public.macro_observations,
  public.embedding_profiles,
  public.chunk_embeddings
to anon, authenticated;
grant select, insert, delete on public.watchlists to authenticated;
grant select, insert on public.analysis_runs, public.agent_outputs,
  public.claim_evidence, public.token_usage to authenticated;
grant usage, select on sequence public.agent_outputs_id_seq, public.token_usage_id_seq
  to authenticated;

alter table public.stocks enable row level security;
alter table public.stock_prices enable row level security;
alter table public.stock_price_history enable row level security;
alter table public.technical_indicators enable row level security;
alter table public.financial_facts enable row level security;
alter table public.evidence_documents enable row level security;
alter table public.evidence_chunks enable row level security;
alter table public.macro_series enable row level security;
alter table public.macro_observations enable row level security;
alter table public.embedding_profiles enable row level security;
alter table public.chunk_embeddings enable row level security;
alter table public.watchlists enable row level security;
alter table public.analysis_runs enable row level security;
alter table public.agent_outputs enable row level security;
alter table public.claim_evidence enable row level security;
alter table public.token_usage enable row level security;

drop policy if exists "Public stock catalog is readable" on public.stocks;
create policy "Public stock catalog is readable" on public.stocks
  for select to anon, authenticated using (true);

drop policy if exists "Public stock prices are readable" on public.stock_prices;
create policy "Public stock prices are readable" on public.stock_prices
  for select to anon, authenticated using (true);

drop policy if exists "Public price history are readable" on public.stock_price_history;
create policy "Public price history are readable" on public.stock_price_history
  for select to anon, authenticated using (true);

drop policy if exists "Public indicators are readable" on public.technical_indicators;
create policy "Public indicators are readable" on public.technical_indicators
  for select to anon, authenticated using (true);

drop policy if exists "Public financial facts are readable" on public.financial_facts;
create policy "Public financial facts are readable" on public.financial_facts
  for select to anon, authenticated using (true);

drop policy if exists "Public evidence documents are readable" on public.evidence_documents;
create policy "Public evidence documents are readable" on public.evidence_documents
  for select to anon, authenticated using (true);

drop policy if exists "Public evidence chunks are readable" on public.evidence_chunks;
create policy "Public evidence chunks are readable" on public.evidence_chunks
  for select to anon, authenticated using (true);

drop policy if exists "Public macro series are readable" on public.macro_series;
create policy "Public macro series are readable" on public.macro_series
  for select to anon, authenticated using (true);

drop policy if exists "Public macro observations are readable" on public.macro_observations;
create policy "Public macro observations are readable" on public.macro_observations
  for select to anon, authenticated using (true);

drop policy if exists "Public embedding profiles are readable" on public.embedding_profiles;
create policy "Public embedding profiles are readable" on public.embedding_profiles
  for select to anon, authenticated using (true);

drop policy if exists "Public chunk embeddings are readable" on public.chunk_embeddings;
create policy "Public chunk embeddings are readable" on public.chunk_embeddings
  for select to anon, authenticated using (true);

drop policy if exists "Users can manage their own watchlist" on public.watchlists;
create policy "Users can manage their own watchlist" on public.watchlists
  for all to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read their own analysis runs" on public.analysis_runs;
create policy "Users can read their own analysis runs" on public.analysis_runs
  for select to authenticated using ((select auth.uid()) = user_id);

drop policy if exists "Users can create their own analysis runs" on public.analysis_runs;
create policy "Users can create their own analysis runs" on public.analysis_runs
  for insert to authenticated with check ((select auth.uid()) = user_id);

drop policy if exists "Users can read outputs for their analysis runs" on public.agent_outputs;
create policy "Users can read outputs for their analysis runs" on public.agent_outputs
  for select to authenticated using (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = agent_outputs.analysis_run_id
        and analysis_runs.user_id = (select auth.uid())
    )
  );

drop policy if exists "Users can create outputs for their analysis runs" on public.agent_outputs;
create policy "Users can create outputs for their analysis runs" on public.agent_outputs
  for insert to authenticated with check (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = agent_outputs.analysis_run_id
        and analysis_runs.user_id = (select auth.uid())
    )
  );

drop policy if exists "Users can read evidence links for their analysis runs" on public.claim_evidence;
create policy "Users can read evidence links for their analysis runs" on public.claim_evidence
  for select to authenticated using (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = claim_evidence.analysis_run_id
        and analysis_runs.user_id = (select auth.uid())
    )
  );

drop policy if exists "Users can create evidence links for their analysis runs" on public.claim_evidence;
create policy "Users can create evidence links for their analysis runs" on public.claim_evidence
  for insert to authenticated with check (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = claim_evidence.analysis_run_id
        and analysis_runs.user_id = (select auth.uid())
    )
  );

drop policy if exists "Users can read token usage for their analysis runs" on public.token_usage;
create policy "Users can read token usage for their analysis runs" on public.token_usage
  for select to authenticated using (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = token_usage.analysis_run_id
        and analysis_runs.user_id = (select auth.uid())
    )
  );

drop policy if exists "Users can create token usage for their analysis runs" on public.token_usage;
create policy "Users can create token usage for their analysis runs" on public.token_usage
  for insert to authenticated with check (
    exists (
      select 1 from public.analysis_runs
      where analysis_runs.id = token_usage.analysis_run_id
        and analysis_runs.user_id = (select auth.uid())
    )
  );

commit;
