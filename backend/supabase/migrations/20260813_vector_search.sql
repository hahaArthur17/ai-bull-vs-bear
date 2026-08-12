create or replace function public.local_text_embedding(input_text text)
returns vector(1536)
language sql
immutable
set search_path = public
as $$
  with tokens as (
    select token
    from regexp_split_to_table(lower(coalesce(input_text, '')), '[^a-z0-9]+') as token
    where length(token) > 2
  ),
  buckets as (
    select
      mod(hashtextextended(token, 0) & 9223372036854775807, 1536)::integer as bucket,
      count(*)::real as weight
    from tokens
    group by 1
  )
  select array_agg(coalesce(buckets.weight, 0)::real order by dimension)::vector(1536)
  from generate_series(0, 1535) as dimension
  left join buckets on buckets.bucket = dimension;
$$;

create or replace function public.match_evidence_chunks(
  query_embedding vector(1536),
  match_count integer default 6,
  filter_ticker text default null,
  filter_source_type text default null
)
returns table (
  chunk_id bigint,
  document_id bigint,
  ticker text,
  source_type text,
  title text,
  url text,
  published_at timestamptz,
  chunk_text text,
  metadata jsonb,
  similarity double precision
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    chunks.id,
    documents.id,
    stocks.ticker,
    documents.source_type,
    documents.title,
    documents.url,
    documents.published_at,
    chunks.chunk_text,
    chunks.metadata,
    1 - (chunks.embedding <=> query_embedding) as similarity
  from public.evidence_chunks as chunks
  join public.evidence_documents as documents on documents.id = chunks.document_id
  join public.stocks on stocks.id = documents.stock_id
  where chunks.embedding is not null
    and (filter_ticker is null or stocks.ticker = upper(filter_ticker))
    and (filter_source_type is null or documents.source_type = filter_source_type)
  order by chunks.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;

grant execute on function public.match_evidence_chunks(vector, integer, text, text)
to anon, authenticated;
