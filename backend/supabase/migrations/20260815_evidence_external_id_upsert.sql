-- PostgREST must be able to infer a complete unique index for
-- on_conflict=external_id. PostgreSQL unique indexes already permit multiple
-- NULL values, so the former partial predicate was unnecessary.

drop index if exists public.evidence_documents_external_id_idx;
create unique index evidence_documents_external_id_idx
  on public.evidence_documents (external_id);
