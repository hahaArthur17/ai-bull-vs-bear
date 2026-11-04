"""Shared, credential-free API lifecycle for UI tests and project review."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def free_port(requested: int = 0) -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", requested))
        return int(probe.getsockname()[1])


def review_environment(api_port: int, web_port: int = 8097) -> dict[str, str]:
    environment = os.environ.copy()
    # This complete profile wins over any developer .env credentials and flags.
    # Review and UI regression runs must never call hosted services or models.
    environment.update(
        {
            "ENVIRONMENT": "test",
            "APP_DATA_MODE": "review_fixture",
            "AUTH_MODE": "demo",
            "PERSISTENCE_MODE": "demo",
            "ANALYSIS_PROVIDER": "demo",
            "DEBATE_INTERRUPTIONS_ENABLED": "true",
            "CORS_ORIGINS": f"http://127.0.0.1:{web_port}",
            "EXPO_NO_DOTENV": "1",
            "EXPO_PUBLIC_AUTH_MODE": "demo",
            "EXPO_PUBLIC_API_URL": f"http://127.0.0.1:{api_port}",
            "EXPO_PUBLIC_DEBATE_V2_ENABLED": "true",
            "EXPO_PUBLIC_DEBATE_INTERRUPTIONS_ENABLED": "true",
            "EXPO_PUBLIC_SUPABASE_URL": "http://127.0.0.1",
            "EXPO_PUBLIC_SUPABASE_ANON_KEY": "review-public-key",
        }
    )
    return environment


def python_executable() -> str:
    project_python = ROOT / "backend/.venv/bin/python"
    return str(project_python) if project_python.exists() else sys.executable


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@contextmanager
def review_api(api_port: int = 0, web_port: int = 8097):
    port = free_port(api_port)
    environment = review_environment(port, web_port)
    with tempfile.TemporaryFile(mode="w+") as log:
        process = subprocess.Popen(
            [
                python_executable(),
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT / "backend",
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            ready = False
            for _ in range(100):
                if process.poll() is not None:
                    break
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=0.5) as response:
                        if json.load(response).get("data_mode") == "review_fixture":
                            ready = True
                except (URLError, TimeoutError):
                    pass
                if ready:
                    break
                time.sleep(0.1)
            if not ready:
                log.seek(0)
                raise RuntimeError(f"Local review API did not start:\n{log.read()}")
            yield environment
        finally:
            stop_process(process)
