-- Alpha Vantage's free weekly endpoint supplies longer history without
-- mislabelling a weekly close as a daily candle.

create table if not exists public.stock_price_history (
  stock_id bigint not null references public.stocks(id) on delete cascade,
  frequency text not null check (frequency in ('weekly')),
  trading_date date not null,
  open numeric(14, 4) not null,
  high numeric(14, 4) not null,
  low numeric(14, 4) not null,
  close numeric(14, 4) not null,
  volume bigint not null,
  source text not null check (source in ('alpha_vantage_weekly')),
  metadata jsonb not null default '{}'::jsonb,
  retrieved_at timestamptz not null default now(),
  primary key (stock_id, frequency, trading_date)
);

create index if not exists stock_price_history_recent_idx
  on public.stock_price_history (stock_id, frequency, trading_date desc);

alter table public.stock_price_history enable row level security;

drop policy if exists "Public price history is readable" on public.stock_price_history;
create policy "Public price history is readable"
  on public.stock_price_history for select using (true);

grant select on table public.stock_price_history to anon, authenticated;
