-- Keep canonical chunks independent from provider-specific vector spaces.
-- Existing 1,536-dimensional database-local hashes remain available as the
-- deterministic local-hash-v1 profile.

create table if not exists public.embedding_profiles (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  provider text not null,
  model text not null,
  dimensions integer not null check (dimensions between 1 and 16000),
  distance_metric text not null default 'cosine'
    check (distance_metric in ('cosine', 'inner_product', 'l2')),
  normalization text not null default 'none',
  modality text not null default 'text'
    check (modality in ('text', 'multimodal')),
  query_instruction text,
  document_instruction text,
  preprocessing_version text not null default 'v1',
  status text not null default 'test'
    check (status in ('test', 'active', 'retired')),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

insert into public.embedding_profiles (
  id,
  slug,
  provider,
  model,
  dimensions,
  distance_metric,
  normalization,
  modality,
  preprocessing_version,
  status,
  metadata
)
values (
  '00000000-0000-4000-8000-000000001536',
  'local-hash-v1',
  'postgres',
  'local_text_embedding',
  1536,
  'cosine',
  'none',
  'text',
  'word-hash-v1',
  'active',
  '{"purpose":"offline integration baseline","semantic_model":false}'::jsonb
)
on conflict (slug) do update set
  provider = excluded.provider,
  model = excluded.model,
  dimensions = excluded.dimensions,
  distance_metric = excluded.distance_metric,
  normalization = excluded.normalization,
  modality = excluded.modality,
  preprocessing_version = excluded.preprocessing_version,
  status = excluded.status,
  metadata = excluded.metadata;

create table if not exists public.chunk_embeddings (
  chunk_id bigint not null references public.evidence_chunks(id) on delete cascade,
  profile_id uuid not null references public.embedding_profiles(id) on delete cascade,
  embedding vector not null,
  input_hash text not null,
  created_at timestamptz not null default now(),
  primary key (chunk_id, profile_id)
);

create or replace function public.validate_chunk_embedding_dimensions()
returns trigger
language plpgsql
set search_path = public
as $$
declare
  expected_dimensions integer;
begin
  select profiles.dimensions
  into expected_dimensions
  from public.embedding_profiles as profiles
  where profiles.id = new.profile_id;

  if expected_dimensions is null then
    raise exception 'Unknown embedding profile %', new.profile_id
      using errcode = '23503';
  end if;

  if vector_dims(new.embedding) <> expected_dimensions then
    raise exception 'Embedding has % dimensions; profile requires %',
      vector_dims(new.embedding), expected_dimensions
      using errcode = '22023';
  end if;

  return new;
end;
$$;

drop trigger if exists chunk_embeddings_validate_dimensions on public.chunk_embeddings;
create trigger chunk_embeddings_validate_dimensions
before insert or update of profile_id, embedding on public.chunk_embeddings
for each row execute function public.validate_chunk_embedding_dimensions();

insert into public.chunk_embeddings (chunk_id, profile_id, embedding, input_hash)
select
  chunks.id,
  '00000000-0000-4000-8000-000000001536'::uuid,
  chunks.embedding,
  md5(chunks.chunk_text)
from public.evidence_chunks as chunks
where chunks.embedding is not null
on conflict (chunk_id, profile_id) do update set
  embedding = excluded.embedding,
  input_hash = excluded.input_hash,
  created_at = now();

create index if not exists chunk_embeddings_local_hash_hnsw_idx
  on public.chunk_embeddings using hnsw
  ((embedding::vector(1536)) vector_cosine_ops)
  where profile_id = '00000000-0000-4000-8000-000000001536'::uuid;

create or replace function public.sync_local_chunk_embedding_profile()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.embedding is not null then
    insert into public.chunk_embeddings (chunk_id, profile_id, embedding, input_hash)
    values (
      new.id,
      '00000000-0000-4000-8000-000000001536'::uuid,
      new.embedding,
      md5(new.chunk_text)
    )
    on conflict (chunk_id, profile_id) do update set
      embedding = excluded.embedding,
      input_hash = excluded.input_hash,
      created_at = now();
  end if;
  return new;
end;
$$;

drop trigger if exists evidence_chunks_sync_local_profile on public.evidence_chunks;
create trigger evidence_chunks_sync_local_profile
after insert or update of chunk_text, embedding on public.evidence_chunks
for each row execute function public.sync_local_chunk_embedding_profile();

create or replace function public.match_evidence_chunks(
  query_text text,
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
    1 - (
      embeddings.embedding::vector(1536)
      <=> public.local_text_embedding(query_text)
    ) as similarity
  from public.chunk_embeddings as embeddings
  join public.evidence_chunks as chunks on chunks.id = embeddings.chunk_id
  join public.evidence_documents as documents on documents.id = chunks.document_id
  join public.stocks on stocks.id = documents.stock_id
  where embeddings.profile_id = '00000000-0000-4000-8000-000000001536'::uuid
    and (filter_ticker is null or stocks.ticker = upper(filter_ticker))
    and (filter_source_type is null or documents.source_type = filter_source_type)
  order by
    embeddings.embedding::vector(1536)
    <=> public.local_text_embedding(query_text)
  limit greatest(match_count, 1);
$$;

create or replace function public.match_evidence_chunks_by_embedding(
  query_embedding vector,
  embedding_profile_slug text,
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
  profile_slug text,
  similarity double precision
)
language plpgsql
stable
security invoker
set search_path = public
as $$
declare
  selected_profile_id uuid;
  selected_dimensions integer;
begin
  select profiles.id, profiles.dimensions
  into selected_profile_id, selected_dimensions
  from public.embedding_profiles as profiles
  where profiles.slug = embedding_profile_slug
    and profiles.status in ('test', 'active');

  if selected_profile_id is null then
    raise exception 'Unknown or inactive embedding profile %', embedding_profile_slug
      using errcode = '22023';
  end if;

  if vector_dims(query_embedding) <> selected_dimensions then
    raise exception 'Query embedding has % dimensions; profile requires %',
      vector_dims(query_embedding), selected_dimensions
      using errcode = '22023';
  end if;

  return query
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
    embedding_profile_slug,
    1 - (embeddings.embedding <=> query_embedding) as similarity
  from public.chunk_embeddings as embeddings
  join public.evidence_chunks as chunks on chunks.id = embeddings.chunk_id
  join public.evidence_documents as documents on documents.id = chunks.document_id
  join public.stocks on stocks.id = documents.stock_id
  where embeddings.profile_id = selected_profile_id
    and vector_dims(embeddings.embedding) = selected_dimensions
    and (filter_ticker is null or stocks.ticker = upper(filter_ticker))
    and (filter_source_type is null or documents.source_type = filter_source_type)
  order by embeddings.embedding <=> query_embedding
  limit greatest(match_count, 1);
end;
$$;

alter table public.embedding_profiles enable row level security;
alter table public.chunk_embeddings enable row level security;

drop policy if exists "Public embedding profiles are readable"
  on public.embedding_profiles;
create policy "Public embedding profiles are readable"
  on public.embedding_profiles for select using (true);

drop policy if exists "Public chunk embeddings are readable"
  on public.chunk_embeddings;
create policy "Public chunk embeddings are readable"
  on public.chunk_embeddings for select using (true);

grant select on table public.embedding_profiles, public.chunk_embeddings
to anon, authenticated;

grant execute on function public.match_evidence_chunks(text, integer, text, text)
to anon, authenticated;
grant execute on function public.match_evidence_chunks_by_embedding(
  vector,
  text,
  integer,
  text,
  text
)
to anon, authenticated;
