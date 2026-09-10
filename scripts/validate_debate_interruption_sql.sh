#!/bin/sh
set -eu

if [ -z "${PG_BIN:-}" ]; then
  if command -v pg_config >/dev/null 2>&1; then
    PG_CONFIG_BIN=$(pg_config --bindir)
    if [ -x "$PG_CONFIG_BIN/postgres" ]; then
      PG_BIN=$PG_CONFIG_BIN
    fi
  fi
  if [ -z "${PG_BIN:-}" ] && command -v brew >/dev/null 2>&1; then
    PG_BIN=$(brew --prefix postgresql@17)/bin
  elif [ -z "${PG_BIN:-}" ] && [ -x /opt/homebrew/opt/postgresql@17/bin/postgres ]; then
    PG_BIN=/opt/homebrew/opt/postgresql@17/bin
  elif [ -z "${PG_BIN:-}" ] && [ -x /usr/local/opt/postgresql@17/bin/postgres ]; then
    PG_BIN=/usr/local/opt/postgresql@17/bin
  fi
  if [ -z "${PG_BIN:-}" ]; then
    echo "PostgreSQL tools were not found; set PG_BIN to their bin directory" >&2
    exit 1
  fi
fi
for executable in initdb postgres pg_isready psql; do
  if [ ! -x "$PG_BIN/$executable" ]; then
    echo "Required PostgreSQL executable is missing: $PG_BIN/$executable" >&2
    exit 1
  fi
done
REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PG_TMP_ROOT=${TMPDIR:-/tmp}
PG_TMP=$(mktemp -d "$PG_TMP_ROOT/debate-interruption-pg.XXXXXX")
PG_DATA="$PG_TMP/data"
PG_SOCKET="$PG_TMP/socket"
PG_LOG="$PG_TMP/postgres.log"
mkdir -p "$PG_SOCKET"

cleanup() {
  if [ -n "${PG_PID:-}" ]; then
    kill "$PG_PID" >/dev/null 2>&1 || true
    wait "$PG_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$PG_TMP"
}
trap cleanup EXIT HUP INT TERM

"$PG_BIN/initdb" -D "$PG_DATA" -A trust --no-locale >/dev/null
"$PG_BIN/postgres" -D "$PG_DATA" -k "$PG_SOCKET" -h "" >"$PG_LOG" 2>&1 &
PG_PID=$!
ready_attempts=0
until "$PG_BIN/pg_isready" -h "$PG_SOCKET" -d postgres >/dev/null 2>&1; do
  ready_attempts=$((ready_attempts + 1))
  if [ "$ready_attempts" -ge 50 ] || ! kill -0 "$PG_PID" >/dev/null 2>&1; then
    cat "$PG_LOG" >&2
    exit 1
  fi
  sleep 0.1
done

psql_run() {
  "$PG_BIN/psql" -X -v ON_ERROR_STOP=1 -h "$PG_SOCKET" -d postgres "$@"
}

psql_run <<'SQL'
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create table auth.users (id uuid primary key);
create function auth.uid() returns uuid language sql stable as
  'select nullif(current_setting(''request.jwt.claim.sub'', true), '''')::uuid';
create table public.stocks (id bigint primary key);
SQL

psql_run -f "$REPO_ROOT/backend/supabase/migrations/20260827_v2_debate_persistence.sql" >/dev/null
psql_run -f "$REPO_ROOT/backend/supabase/migrations/20260909_debate_draft_interruption.sql" >/dev/null
psql_run -f "$REPO_ROOT/backend/supabase/migrations/20260909_debate_draft_interruption.sql" >/dev/null
psql_run -f "$REPO_ROOT/backend/tests/sql/test_debate_draft_interruption.sql"
