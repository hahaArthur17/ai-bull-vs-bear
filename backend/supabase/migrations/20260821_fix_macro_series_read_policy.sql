-- The initial macro migration is intended to expose public source metadata to
-- the cache-reading frontend. Reassert the grant and RLS policy for databases
-- where the original policy was not present after migration application.

grant select on table public.macro_series to anon, authenticated;

drop policy if exists "Public macro series are readable" on public.macro_series;
create policy "Public macro series are readable"
  on public.macro_series for select using (true);
