-- Public stock, price, indicator, and evidence data is read-only. RLS remains
-- enabled so writes are not accidentally exposed through the Data API.

alter table public.stocks enable row level security;
alter table public.stock_prices enable row level security;
alter table public.technical_indicators enable row level security;
alter table public.evidence_documents enable row level security;
alter table public.evidence_chunks enable row level security;

drop policy if exists "Public stocks are readable" on public.stocks;
create policy "Public stocks are readable"
  on public.stocks for select using (true);

drop policy if exists "Public stock prices are readable" on public.stock_prices;
create policy "Public stock prices are readable"
  on public.stock_prices for select using (true);

drop policy if exists "Public indicators are readable" on public.technical_indicators;
create policy "Public indicators are readable"
  on public.technical_indicators for select using (true);

drop policy if exists "Public evidence documents are readable" on public.evidence_documents;
create policy "Public evidence documents are readable"
  on public.evidence_documents for select using (true);

drop policy if exists "Public evidence chunks are readable" on public.evidence_chunks;
create policy "Public evidence chunks are readable"
  on public.evidence_chunks for select using (true);
