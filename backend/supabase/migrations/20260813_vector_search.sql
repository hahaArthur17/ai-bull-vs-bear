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
