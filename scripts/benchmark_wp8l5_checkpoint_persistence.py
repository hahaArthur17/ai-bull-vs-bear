#!/usr/bin/env python3
"""Measure local WP8L.5 draft checkpoint persistence.

The benchmark boots an isolated PostgreSQL cluster in a temporary directory,
applies the checked-in Debate persistence and draft interruption migrations,
and issues one ``checkpoint_debate_draft`` call for every generated delta.
Calls use the local Unix socket and are timed by psql, so the result includes
the local client/server round trip without contacting Supabase or a provider.

The workload keeps one message identity and appends a deterministic fixed-size
delta on every call.  The migration's upsert and prefix guard therefore see
the same shape as a streaming draft.  The final row is checked for exactly one
checkpoint and the expected complete prefix.  Thresholds are deliberately
command-line options so a CI job or a developer can choose its own budget.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parents[1]
PERSISTENCE_MIGRATION = REPO_ROOT / "backend/supabase/migrations/20260827_v2_debate_persistence.sql"
INTERRUPTION_MIGRATION = REPO_ROOT / "backend/supabase/migrations/20260909_debate_draft_interruption.sql"
TIMING_PATTERN = re.compile(r"^Time:\s*([0-9]+(?:\.[0-9]+)?)\s+ms\s*$", re.MULTILINE)

SESSION_ID = "10000000-0000-0000-0000-000000000001"
USER_ID = "00000000-0000-0000-0000-000000000001"
BRANCH_ID = "20000000-0000-0000-0000-000000000001"
GENERATION_ID = "30000000-0000-0000-0000-000000000001"
MESSAGE_ID = "50000000-0000-0000-0000-000000000001"


def nonnegative_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a finite non-negative number")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Measure local WP8L.5 draft checkpoint latency and request volume."
    )
    parser.add_argument(
        "--samples",
        type=positive_int,
        default=120,
        help="Number of sequential checkpoint RPCs/deltas (default: 120).",
    )
    parser.add_argument(
        "--delta-chars",
        type=positive_int,
        default=28,
        help="Fixed UTF-8/ASCII characters appended per delta (default: 28).",
    )
    parser.add_argument(
        "--max-requests",
        type=nonnegative_int,
        default=None,
        help="Maximum allowed checkpoint RPCs (default: exactly --samples).",
    )
    parser.add_argument(
        "--max-p50-ms",
        type=nonnegative_float,
        default=5.0,
        help="Maximum p50 checkpoint latency in milliseconds (default: 5).",
    )
    parser.add_argument(
        "--max-p95-ms",
        type=nonnegative_float,
        default=10.0,
        help="Maximum p95 checkpoint latency in milliseconds (default: 10).",
    )
    parser.add_argument(
        "--max-p99-ms",
        type=nonnegative_float,
        default=20.0,
        help="Maximum p99 checkpoint latency in milliseconds (default: 20).",
    )
    parser.add_argument(
        "--max-mean-ms",
        type=nonnegative_float,
        default=10.0,
        help="Maximum mean checkpoint latency in milliseconds (default: 10).",
    )
    parser.add_argument(
        "--max-max-ms",
        type=nonnegative_float,
        default=50.0,
        help="Maximum individual checkpoint latency in milliseconds (default: 50).",
    )
    parser.add_argument(
        "--pg-bin",
        type=Path,
        default=None,
        help="PostgreSQL bin directory; otherwise PG_BIN/pg_config/Homebrew is used.",
    )
    return parser.parse_args()


def resolve_pg_bin(requested: Path | None) -> Path:
    candidates: list[Path] = []
    if requested is not None:
        candidates.append(requested)
    env_bin = os.environ.get("PG_BIN")
    if env_bin:
        candidates.append(Path(env_bin))

    pg_config = shutil.which("pg_config")
    if pg_config:
        try:
            configured_bin = subprocess.check_output(
                [pg_config, "--bindir"],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=10,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            configured_bin = ""
        if configured_bin:
            candidates.append(Path(configured_bin))

    candidates.extend(
        [
            Path("/opt/homebrew/opt/postgresql@17/bin"),
            Path("/usr/local/opt/postgresql@17/bin"),
        ]
    )
    required = ("initdb", "postgres", "pg_isready", "psql")
    for candidate in candidates:
        if all((candidate / executable).is_file() and os.access(candidate / executable, os.X_OK)
               for executable in required):
            return candidate
    searched = ", ".join(str(item) for item in candidates if str(item))
    raise RuntimeError(
        "PostgreSQL tools were not found; set PG_BIN or pass --pg-bin "
        f"(searched: {searched})"
    )


@contextmanager
def temporary_postgres(pg_bin: Path) -> Iterator[tuple[Path, Path]]:
    temporary_root = Path(tempfile.mkdtemp(prefix="wp8l5-checkpoint-pg-"))
    data_dir = temporary_root / "data"
    socket_dir = temporary_root / "socket"
    log_path = temporary_root / "postgres.log"
    socket_dir.mkdir()
    postgres_process: subprocess.Popen[bytes] | None = None
    log_handle = None
    try:
        initdb = subprocess.run(
            [str(pg_bin / "initdb"), "-D", str(data_dir), "-A", "trust", "--no-locale"],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if initdb.returncode != 0:
            raise RuntimeError(f"initdb failed:\n{initdb.stdout}\n{initdb.stderr}")

        log_handle = log_path.open("w", encoding="utf-8")
        postgres_process = subprocess.Popen(
            [
                str(pg_bin / "postgres"),
                "-D",
                str(data_dir),
                "-k",
                str(socket_dir),
                "-h",
                "",
            ],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        ready = False
        for _ in range(60):
            if postgres_process.poll() is not None:
                break
            probe = subprocess.run(
                [str(pg_bin / "pg_isready"), "-h", str(socket_dir), "-d", "postgres"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if probe.returncode == 0:
                ready = True
                break
            time.sleep(0.1)
        if not ready:
            log_handle.flush()
            details = log_path.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(f"temporary PostgreSQL did not become ready:\n{details}")
        yield data_dir, socket_dir
    finally:
        if postgres_process is not None:
            if postgres_process.poll() is None:
                postgres_process.send_signal(signal.SIGTERM)
                try:
                    postgres_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    postgres_process.kill()
                    postgres_process.wait(timeout=5)
        if log_handle is not None:
            log_handle.close()
        shutil.rmtree(temporary_root, ignore_errors=True)


def psql_command(pg_bin: Path, socket_dir: Path, *extra: str) -> list[str]:
    return [
        str(pg_bin / "psql"),
        "-X",
        "-v",
        "ON_ERROR_STOP=1",
        "-h",
        str(socket_dir),
        "-d",
        "postgres",
        *extra,
    ]


def run_psql(
    pg_bin: Path,
    socket_dir: Path,
    *,
    sql: str | None = None,
    file: Path | None = None,
    extra: tuple[str, ...] = (),
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    command = psql_command(pg_bin, socket_dir, *extra)
    if file is not None:
        command.extend(("-f", str(file)))
    environment = os.environ.copy()
    environment["LC_ALL"] = "C"
    result = subprocess.run(
        command,
        input=sql,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        env=environment,
        timeout=timeout,
    )
    if result.returncode != 0:
        detail = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
        raise RuntimeError(f"psql failed with status {result.returncode}:\n{detail}")
    return result


def bootstrap_database(pg_bin: Path, socket_dir: Path) -> None:
    run_psql(
        pg_bin,
        socket_dir,
        sql="""
create role anon nologin;
create role authenticated nologin;
create role service_role nologin bypassrls;
create schema auth;
create table auth.users (id uuid primary key);
create function auth.uid() returns uuid language sql stable as
  'select nullif(current_setting(''request.jwt.claim.sub'', true), '''')::uuid';
create table public.stocks (id bigint primary key);
""",
    )
    run_psql(pg_bin, socket_dir, file=PERSISTENCE_MIGRATION)
    run_psql(pg_bin, socket_dir, file=INTERRUPTION_MIGRATION)
    run_psql(
        pg_bin,
        socket_dir,
        sql=f"""
insert into auth.users(id) values ('{USER_ID}');
insert into public.stocks(id) values (1);
insert into public.debate_sessions(
  id,user_id,stock_id,ticker,mode,status,opening_side,active_branch_id,
  active_generation_id,analysis_context,factor_snapshot,guardrail_status,
  created_at,updated_at
) values (
  '{SESSION_ID}','{USER_ID}',1,'TEST','demo','running_round_1','bull',
  '{BRANCH_ID}','{GENERATION_ID}','{{}}','{{}}','passed',
  '2026-09-10 00:00:00+00','2026-09-10 00:00:00+00'
);
""",
    )


def make_prefixes(samples: int, delta_chars: int) -> list[str]:
    prefixes: list[str] = []
    running = ""
    for index in range(1, samples + 1):
        label = f"d{index:04d}:"
        if len(label) > delta_chars:
            raise ValueError(
                f"--delta-chars must be at least {len(label)} for sample {index}"
            )
        running += label + ("x" * (delta_chars - len(label)))
        if len(running) > 6000:
            raise ValueError(
                f"generated content is {len(running)} characters; the migration limit is 6000"
            )
        prefixes.append(running)
    return prefixes


def sql_string(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def checkpoint_statement(content: str, index: int) -> str:
    return f"""select public.checkpoint_debate_draft(jsonb_build_object(
  'id',{sql_string(MESSAGE_ID)},
  'session_id',{sql_string(SESSION_ID)},
  'branch_id',{sql_string(BRANCH_ID)},
  'generation_id',{sql_string(GENERATION_ID)},
  'sequence_number',1,'round_number',1,'exchange_number',1,
  'role','bull','message_kind','argument','content',{sql_string(content)},
  'terms',jsonb_build_array(),
  'metadata',jsonb_build_object('benchmark','wp8l5','delta_number',{index}),
  'is_complete',false,'cancelled_at',null,
  'created_at','2026-09-10 00:00:00+00'
));"""


def workload_sql(prefixes: list[str]) -> str:
    statements = [
        "\\set ON_ERROR_STOP on",
        "\\pset pager off",
        "\\pset tuples_only on",
        "\\pset format unaligned",
        "set role service_role;",
        "\\timing on",
    ]
    statements.extend(
        checkpoint_statement(content, index)
        for index, content in enumerate(prefixes, start=1)
    )
    statements.extend(("\\timing off", "reset role;"))
    return "\n".join(statements) + "\n"


def parse_timings(result: subprocess.CompletedProcess[str]) -> list[float]:
    # psql writes timing diagnostics to stdout today; inspect both streams to
    # keep this parser stable across psql builds and output configurations.
    combined = "\n".join((result.stdout, result.stderr))
    return [float(item) for item in TIMING_PATTERN.findall(combined)]


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("cannot calculate a percentile for an empty sample")
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": percentile(values, 0.50),
        "p95_ms": percentile(values, 0.95),
        "p99_ms": percentile(values, 0.99),
        "mean_ms": sum(values) / len(values),
        "min_ms": min(values),
        "max_ms": max(values),
    }


def persisted_checkpoint(
    pg_bin: Path,
    socket_dir: Path,
) -> dict[str, object]:
    result = run_psql(
        pg_bin,
        socket_dir,
        extra=("-At",),
        sql=f"""
set role service_role;
select json_build_object(
  'row_count',(select count(*) from public.debate_draft_checkpoints),
  'message_id',(select message_id::text from public.debate_draft_checkpoints limit 1),
  'session_id',(select session_id::text from public.debate_draft_checkpoints limit 1),
  'generation_id',(select payload->>'generation_id' from public.debate_draft_checkpoints limit 1),
  'sequence_number',(select payload->>'sequence_number' from public.debate_draft_checkpoints limit 1),
  'content',(select payload->>'content' from public.debate_draft_checkpoints limit 1)
)::text;
reset role;
""",
    )
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not rows:
        raise RuntimeError("checkpoint verification returned no row")
    payload = None
    for row in rows:
        try:
            candidate = json.loads(row)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if payload is None:
        raise RuntimeError(f"checkpoint verification returned no JSON object: {rows}")
    return payload


def rounded_summary(summary: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 3) for key, value in summary.items()}


def run_benchmark(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    pg_bin = resolve_pg_bin(args.pg_bin)
    prefixes = make_prefixes(args.samples, args.delta_chars)
    max_requests = args.max_requests if args.max_requests is not None else args.samples
    generated_prefixes_valid = all(
        current.startswith(previous)
        for previous, current in zip(prefixes, prefixes[1:])
    )

    with temporary_postgres(pg_bin) as (_, socket_dir):
        bootstrap_database(pg_bin, socket_dir)
        timed = run_psql(pg_bin, socket_dir, sql=workload_sql(prefixes))
        timings = parse_timings(timed)
        if len(timings) != len(prefixes):
            raise RuntimeError(
                f"expected {len(prefixes)} psql timings for checkpoint RPCs, got {len(timings)}"
            )
        stored = persisted_checkpoint(pg_bin, socket_dir)

    summary = summarize(timings)
    persisted_final_prefix = (
        stored.get("row_count") == 1
        and stored.get("message_id") == MESSAGE_ID
        and stored.get("session_id") == SESSION_ID
        and stored.get("generation_id") == GENERATION_ID
        and stored.get("sequence_number") == "1"
        and stored.get("content") == prefixes[-1]
    )
    prefix_progression_valid = generated_prefixes_valid and persisted_final_prefix
    request_count = len(timings)
    budget_checks = {
        "request_count": {
            "observed": request_count,
            "maximum": max_requests,
            "passed": request_count <= max_requests,
        },
        "p50_ms": {
            "observed": round(summary["p50_ms"], 3),
            "maximum": args.max_p50_ms,
            "passed": summary["p50_ms"] <= args.max_p50_ms,
        },
        "p95_ms": {
            "observed": round(summary["p95_ms"], 3),
            "maximum": args.max_p95_ms,
            "passed": summary["p95_ms"] <= args.max_p95_ms,
        },
        "p99_ms": {
            "observed": round(summary["p99_ms"], 3),
            "maximum": args.max_p99_ms,
            "passed": summary["p99_ms"] <= args.max_p99_ms,
        },
        "mean_ms": {
            "observed": round(summary["mean_ms"], 3),
            "maximum": args.max_mean_ms,
            "passed": summary["mean_ms"] <= args.max_mean_ms,
        },
        "max_ms": {
            "observed": round(summary["max_ms"], 3),
            "maximum": args.max_max_ms,
            "passed": summary["max_ms"] <= args.max_max_ms,
        },
    }
    passed = prefix_progression_valid and all(
        check["passed"] for check in budget_checks.values()
    )
    report: dict[str, object] = {
        "benchmark": "WP8L.5 draft checkpoint persistence",
        "passed": passed,
        "database": "isolated temporary PostgreSQL over a local Unix socket",
        "migrations": [
            str(PERSISTENCE_MIGRATION.relative_to(REPO_ROOT)),
            str(INTERRUPTION_MIGRATION.relative_to(REPO_ROOT)),
        ],
        "workload": {
            "samples": args.samples,
            "delta_chars": args.delta_chars,
            "final_content_chars": len(prefixes[-1]),
            "checkpoint_rpc_requests": request_count,
            "requests_per_delta": request_count / args.samples,
        },
        "latency_ms": rounded_summary(summary),
        "prefix_progression": {
            "generated_prefix_chain": generated_prefixes_valid,
            "persisted_final_prefix": persisted_final_prefix,
            "valid": prefix_progression_valid,
        },
        "budgets": budget_checks,
    }
    return report, 0 if passed else 2


def main() -> int:
    args = parse_args()
    try:
        report, status = run_benchmark(args)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(f"WP8L.5 checkpoint benchmark failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
