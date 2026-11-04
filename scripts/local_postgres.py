"""Isolated PostgreSQL lifecycle for local SQL tests and benchmarks.

No hosted connection string or developer credentials are used. The temporary
cluster accepts connections only through its private Unix socket.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

REPO_ROOT = Path(__file__).resolve().parents[1]


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
        if all(
            (candidate / executable).is_file() and os.access(candidate / executable, os.X_OK)
            for executable in required
        ):
            return candidate
    searched = ", ".join(str(item) for item in candidates if str(item))
    raise RuntimeError(
        f"PostgreSQL tools were not found; set PG_BIN or pass --pg-bin (searched: {searched})"
    )


@contextmanager
def temporary_postgres(pg_bin: Path) -> Iterator[tuple[Path, Path]]:
    temporary_root = Path(tempfile.mkdtemp(prefix="bullbear-test-pg-"))
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
