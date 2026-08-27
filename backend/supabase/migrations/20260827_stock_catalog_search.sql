-- Ranked, bounded catalog search. This function reads only local Postgres rows
-- and never calls a market-data or external catalog provider.

create or replace function public.search_stock_catalog(
  search_query text,
  result_limit integer default 20
)
returns table (
  ticker text,
  company_name text,
  exchange text,
  sector text,
  sec_cik bigint,
  country text,
  aliases text[],
  is_active boolean,
  coverage_status text,
  coverage_updated_at timestamptz
)
language sql
stable
set search_path = ''
as $$
  with normalized as (
    select
      translate(
        lower(btrim(coalesce(search_query, ''))),
        chr(37) || chr(95) || chr(92),
        ''
      ) as query,
      least(greatest(coalesce(result_limit, 20), 1), 25) as row_limit
  )
  select
    stock.ticker,
    stock.company_name,
    stock.exchange,
    stock.sector,
    stock.sec_cik,
    stock.country,
    stock.aliases,
    stock.is_active,
    stock.coverage_status,
    stock.coverage_updated_at
  from public.stocks as stock
  cross join normalized
  where
    stock.is_active
    and normalized.query <> ''
    and (
      lower(stock.ticker) = normalized.query
      or lower(stock.ticker) like normalized.query || '%'
      or exists (
        select 1 from unnest(stock.aliases) as alias(value)
        where lower(alias.value) = normalized.query
      )
      or (
        length(normalized.query) >= 2
        and lower(stock.company_name) like normalized.query || '%'
      )
      or (
        length(normalized.query) >= 2
        and exists (
          select 1 from unnest(stock.aliases) as alias(value)
          where lower(alias.value) like normalized.query || '%'
        )
      )
      or (
        length(normalized.query) >= 3
        and stock.search_text like '%' || normalized.query || '%'
      )
    )
  order by
    case
      when lower(stock.ticker) = normalized.query then 0
      when lower(stock.ticker) like normalized.query || '%' then 1
      when exists (
        select 1 from unnest(stock.aliases) as alias(value)
        where lower(alias.value) = normalized.query
      ) then 2
      when lower(stock.company_name) like normalized.query || '%' then 3
      when exists (
        select 1 from unnest(stock.aliases) as alias(value)
        where lower(alias.value) like normalized.query || '%'
      ) then 4
      else 5
    end,
    stock.ticker
  limit (select row_limit from normalized);
$$;

revoke all on function public.search_stock_catalog(text, integer) from public;
grant execute on function public.search_stock_catalog(text, integer) to anon, authenticated;
