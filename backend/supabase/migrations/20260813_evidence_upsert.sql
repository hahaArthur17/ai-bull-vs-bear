-- External evidence documents have stable provider IDs so repeated ingestion
-- refreshes metadata instead of creating duplicate rows.

create unique index if not exists evidence_documents_external_id_idx
  on public.evidence_documents (external_id)
  where external_id is not null;
