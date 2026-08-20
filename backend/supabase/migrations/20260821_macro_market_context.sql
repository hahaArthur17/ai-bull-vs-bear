-- Cache dated, source-labelled macro observations separately from a stock so
-- Debate can cite market context without presenting it as company news.

create table if not exists public.macro_series (
  code text primary key,
  name text not null,
  source text not null check (source in ('fred', 'eia', 'treasury', 'fomc', 'cme')),
  unit text not null,
  frequency text not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.macro_observations (
  series_code text not null references public.macro_series(code) on delete cascade,
  observation_date date not null,
  value numeric not null,
  metadata jsonb not null default '{}'::jsonb,
  retrieved_at timestamptz not null default now(),
  primary key (series_code, observation_date)
);

create index if not exists macro_observations_recent_idx
  on public.macro_observations (series_code, observation_date desc);

alter table public.macro_series enable row level security;
alter table public.macro_observations enable row level security;

drop policy if exists "Public macro series are readable" on public.macro_series;
create policy "Public macro series are readable"
  on public.macro_series for select using (true);

drop policy if exists "Public macro observations are readable" on public.macro_observations;
create policy "Public macro observations are readable"
  on public.macro_observations for select using (true);

grant select on table public.macro_series, public.macro_observations to anon, authenticated;
