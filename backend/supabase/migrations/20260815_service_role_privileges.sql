-- The project uses explicit Data API grants. Keep anon/authenticated access
-- narrow while restoring the backend service_role's expected administrative
-- privileges for ingestion and maintenance jobs.

grant usage on schema public to service_role;
grant all privileges on all tables in schema public to service_role;
grant all privileges on all sequences in schema public to service_role;

alter default privileges in schema public
  grant all privileges on tables to service_role;
alter default privileges in schema public
  grant all privileges on sequences to service_role;
