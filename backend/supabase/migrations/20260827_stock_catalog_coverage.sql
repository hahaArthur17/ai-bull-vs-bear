-- Add stock identity and capability metadata before importing the SEC snapshot.
-- Catalog presence does not imply price, evidence, or Debate coverage.

create extension if not exists pg_trgm;

alter table public.stocks
  alter column sector drop not null,
  add column if not exists sec_cik bigint,
  add column if not exists country text,
  add column if not exists aliases text[] not null default '{}'::text[],
  add column if not exists search_text text not null default '',
  add column if not exists is_active boolean not null default true,
  add column if not exists coverage_status text not null default 'catalog_only',
  add column if not exists coverage_updated_at timestamptz not null default now();

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'stocks_sec_cik_positive'
      and conrelid = 'public.stocks'::regclass
  ) then
    alter table public.stocks
      add constraint stocks_sec_cik_positive
      check (sec_cik is null or sec_cik > 0);
  end if;
  if not exists (
    select 1 from pg_constraint
    where conname = 'stocks_coverage_status_allowed'
      and conrelid = 'public.stocks'::regclass
  ) then
    alter table public.stocks
      add constraint stocks_coverage_status_allowed
      check (coverage_status in (
        'catalog_only',
        'price_cached',
        'evidence_ready',
        'debate_ready'
      ));
  end if;
end
$$;

update public.stocks
set search_text = lower(concat_ws(' ', ticker, company_name, array_to_string(aliases, ' ')))
where search_text = '';

with demo_stock (
  ticker,
  sec_cik,
  country,
  aliases
) as (
  values
    ('AAPL', 320193::bigint, 'US', array['apple']::text[]),
    ('GOOG', 1652044::bigint, 'US', array['alphabet', 'google']::text[]),
    ('NVDA', 1045810::bigint, 'US', array['nvidia']::text[]),
    ('TSLA', 1318605::bigint, 'US', array['tesla']::text[])
)
update public.stocks as stock
set
  sec_cik = demo_stock.sec_cik,
  country = demo_stock.country,
  aliases = demo_stock.aliases,
  search_text = lower(concat_ws(
    ' ',
    stock.ticker,
    stock.company_name,
    array_to_string(demo_stock.aliases, ' ')
  )),
  is_active = true,
  coverage_status = 'debate_ready',
  coverage_updated_at = '2026-08-27T00:00:00Z'::timestamptz
from demo_stock
where stock.ticker = demo_stock.ticker;

create index if not exists stocks_ticker_lower_idx
  on public.stocks (lower(ticker));

create index if not exists stocks_active_coverage_idx
  on public.stocks (is_active, coverage_status, ticker);

create index if not exists stocks_search_text_trgm_idx
  on public.stocks using gin (search_text gin_trgm_ops);

alter table public.stocks enable row level security;

drop policy if exists "Public stock catalog is readable" on public.stocks;
create policy "Public stock catalog is readable"
  on public.stocks for select
  using (true);
