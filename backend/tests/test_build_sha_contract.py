from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app


SHA = "0123456789abcdef0123456789abcdef01234567"


def test_build_sha_defaults_to_none_and_accepts_an_environment_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APP_BUILD_SHA", raising=False)
    assert Settings(_env_file=None).app_build_sha is None

    monkeypatch.setenv("APP_BUILD_SHA", SHA)
    assert Settings(_env_file=None).app_build_sha == SHA

    monkeypatch.setenv("APP_BUILD_SHA", "")
    assert Settings(_env_file=None).app_build_sha is None


@pytest.mark.parametrize("value", [SHA, "abcdef0", "ABCDEF0123456789"])
def test_build_sha_accepts_7_to_64_hex_characters(value: str) -> None:
    assert Settings(_env_file=None, app_build_sha=value).app_build_sha == value


@pytest.mark.parametrize(
    "value",
    ["abcdef", "g123456", "0123456789abcdef" * 5],
)
def test_build_sha_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_build_sha=value)


def test_health_exposes_build_sha_without_deriving_or_exposing_other_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    monkeypatch.setattr(main.settings, "app_build_sha", SHA)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["build_sha"] == SHA


def test_health_reports_null_when_build_sha_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main

    monkeypatch.setattr(main.settings, "app_build_sha", None)

    assert TestClient(app).get("/health").json()["build_sha"] is None
