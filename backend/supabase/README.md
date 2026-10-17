# Supabase setup

Last reviewed: 2026-10-17.

Supabase Auth/persistence, the catalog, V2 Debate, Queue and interruption
adapters are implemented. Demo defaults remain available without credentials;
code availability does not enable hosted V2 automatically. Historical hosted
verification is recorded in [current status](../../docs/planning/current-status.md)
and [live services setup](../../docs/setup/live-services.md).

## Setup and migration order

1. Use the existing project for this repository, or create a dedicated project
   for a new installation at [Supabase Dashboard](https://supabase.com/dashboard).
2. For a **new database**, run [schema.sql](schema.sql), then the checked-in
   [migrations](migrations) in filename order. For an existing database, inspect
   the applied schema and run only missing changes; do not reset user history.
3. Configure the sign-in method and dedicated non-production acceptance users.
4. Keep project URL/public key and server secret in the ignored root `.env`.
   Set `AUTH_MODE=supabase` and `PERSISTENCE_MODE=supabase` explicitly when ready.
5. Verify public market reads, two-user isolation, rejected direct client writes
   and service-only RPC behavior before enabling dependent features.

The base schema alone is insufficient. Later feature groups depend on all
earlier groups:

| Migration group | Files / boundary |
| --- | --- |
| User persistence, evidence, vectors, facts, market/macro caches | All `20260813_*` through `20260821_*` migrations |
| Catalog coverage/search/seed | `20260827_stock_catalog_coverage.sql`, `20260827_stock_catalog_search.sql`, `20260827_stock_catalog_seed.sql` |
| Five canonical V2 relations and atomic writes | `20260827_v2_debate_persistence.sql`, `20260827_v2_debate_persistence_rpc.sql` |
| Durable Queue and atomic stage admission | `20260828_v2_debate_queue.sql` |
| Draft checkpoints, provider attempts, Stop/interjection/Continue | `20260909_debate_draft_interruption.sql` |
| Service-only Continue, PostgREST conflict status, ambiguous transport replay | All three `20260911_*` migrations |

Review the individual SQL before applying it; a feature flag is not a migration
runner. Before catalog import, preserve the documented 400 MB capacity gate and
15 MiB catalog relation budget. The generated seed has 16 bounded upserts in
one transaction and preserves existing coverage/sector/country/aliases. Never
manually edit generated rows; regenerate from the reviewed catalog artifact.

## Credentials and authorization

The public key can be supplied as backend `SUPABASE_ANON_KEY` and client
`EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (or the legacy anon-key variable), along
with the corresponding URL. `SUPABASE_SECRET_KEY` is server-only and is needed
for ingestion and standard V2 atomic writes/Queue operations. Current
`sb_secret_...` and legacy service-role keys are supported by backend adapters.
See [Supabase key guidance](https://supabase.com/docs/guides/getting-started/api-keys).

Canonical Debate tables have owner-read RLS; direct authenticated writes and
privileged RPC calls are rejected. Draft checkpoints are server-only; provider
attempts have owner-read access. API mutations validate ownership and
state/generation before service-only transactions. Never ship the server secret
through Expo configuration.

## Verification

From the repository root:

```sh
PYTHONPATH=backend backend/.venv/bin/python scripts/verify_supabase_migration_preflight.py
```

This is a read-only schema/API preflight. Follow the separate procedures in
[live services setup](../../docs/setup/live-services.md) for RLS, Debate
persistence, Queue and interruption verifiers. Those verifiers can create
bounded disposable records; retain their reported IDs and clean up only their
own fixtures/Queue messages. Never blanket-purge shared Queue state.

Hosted checks are not part of the ordinary credential-free test suite. This
2026-10-17 documentation pass does not apply migrations or rerun hosted tests.

## Evidence storage

Canonical chunks and provider-specific embeddings are separate. `local-hash-v1`
is the deterministic offline baseline, not a learned semantic model. Future
embedding profiles must not mix similarity comparisons across models/dimensions.
Structured SEC XBRL belongs in `financial_facts`, preserving period/unit and
arithmetic semantics instead of flattening values into vectors.
