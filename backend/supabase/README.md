# Supabase setup

1. Create a Supabase project at https://supabase.com/dashboard.
2. Open SQL Editor and run schema.sql.
3. Enable Email or OAuth authentication under Authentication.
4. Copy the project URL and anon key into a local .env file.
5. Keep ANALYSIS_PROVIDER=demo until the provider adapter is configured.

The current backend intentionally uses the deterministic DemoStore so the
application is usable before Supabase credentials are available. The SQL schema
and environment variables are prepared for the persistence/authentication
milestone.
