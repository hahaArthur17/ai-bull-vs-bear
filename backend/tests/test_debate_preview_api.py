from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import main
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.analysis import AnalysisService
from app.services.debate_preview import DebatePreviewService
from app.services.demo_store import DemoStore


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    store = DemoStore()
    repository = InMemoryDebateRepository()
    provider = DeterministicDebateProvider()
    service = DebatePreviewService(repository, provider, provider)
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "analysis_service", AnalysisService(store))
    monkeypatch.setattr(main, "debate_preview_service", service)
    monkeypatch.setattr(main.settings, "auth_mode", "demo")
    monkeypatch.setattr(main.settings, "debate_workflow_v2", False)


def enable_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main.settings, "debate_workflow_v2", True)


def create_round_one(
    monkeypatch: pytest.MonkeyPatch,
    *,
    user: str = "preview-user",
    ticker: str = "AAPL",
) -> dict[str, object]:
    enable_preview(monkeypatch)
    response = client.post(
        "/debates",
        headers={"X-User-Id": user},
        json={
            "ticker": ticker,
            "question": "Which dated factors support each side?",
            "opening_side": "bull",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_preview_is_hidden_by_default_while_legacy_analysis_still_works() -> None:
    assert client.get("/debates").status_code == 404
    assert client.post("/debates", json={"ticker": "AAPL"}).status_code == 404
    assert "/debates" not in client.get("/openapi.json").json()["paths"]

    legacy = client.post("/analysis/AAPL", json={})

    assert legacy.status_code == 201
    assert legacy.json()["ticker"] == "AAPL"
    assert {"bull", "bear", "judge"} <= legacy.json().keys()


def test_disabled_preview_returns_not_found_before_supabase_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main.settings, "auth_mode", "supabase")

    response = client.get("/debates")

    assert response.status_code == 404
    assert response.json() == {"detail": "Debate V2 is not enabled"}


def test_create_round_one_exposes_three_exchanges_and_interim_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = create_round_one(monkeypatch)
    session = payload["session"]
    messages = payload["messages"]

    assert payload["execution_mode"] == "synchronous_preview"
    assert session["status"] == "awaiting_user"
    assert len(messages) == 7
    assert [record["message"]["role"] for record in messages] == [
        "bull",
        "bear",
        "bull",
        "bear",
        "bull",
        "bear",
        "judge",
    ]
    assert [record["message"]["exchange_number"] for record in messages[:6]] == [
        1,
        1,
        2,
        2,
        3,
        3,
    ]
    assert session["interim_judge_message_id"] == messages[-1]["message"]["id"]
    assert all(record["message"]["is_complete"] for record in messages)
    assert any(record["citations"] for record in messages)

    session_id = session["id"]
    headers = {"X-User-Id": "preview-user"}
    assert client.get("/debates", headers=headers).json()[0]["id"] == session_id
    assert client.get(f"/debates/{session_id}", headers=headers).json() == {
        "session": session,
        "messages": messages,
        "execution_mode": "synchronous_preview",
    }
    assert len(client.get(f"/debates/{session_id}/messages", headers=headers).json()) == 7


def test_catalog_only_stock_is_rejected_before_session_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)

    response = client.post("/debates", json={"ticker": "MSFT"})

    assert response.status_code == 409
    assert "Debate-ready" in response.json()["detail"]
    assert client.get("/debates").json() == []


def test_debate_reads_are_owner_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = create_round_one(monkeypatch, user="owner-a")
    session_id = payload["session"]["id"]

    assert client.get(
        f"/debates/{session_id}",
        headers={"X-User-Id": "owner-b"},
    ).status_code == 404
    assert client.get("/debates", headers={"X-User-Id": "owner-b"}).json() == []
    assert len(client.get("/debates", headers={"X-User-Id": "owner-a"}).json()) == 1


def test_challenge_persists_user_question_and_completes_round_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_round = create_round_one(monkeypatch)
    session_id = first_round["session"]["id"]
    target = first_round["messages"][1]["message"]
    selected_text = target["content"][:40]
    question = "Does this rebuttal underweight the filing risk?"

    response = client.post(
        f"/debates/{session_id}/interventions",
        headers={"X-User-Id": "preview-user"},
        json={
            "selected_message_id": target["id"],
            "selected_text": selected_text,
            "question": question,
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["session"]["status"] == "completed"
    assert len(payload["messages"]) == 13
    assert payload["messages"][7]["message"]["role"] == "user"
    assert payload["messages"][7]["message"]["content"] == question
    assert [record["message"]["role"] for record in payload["messages"][8:]] == [
        "bull",
        "bear",
        "bull",
        "bear",
        "judge",
    ]
    assert payload["session"]["final_judge_message_id"] == payload["messages"][-1][
        "message"
    ]["id"]
    assert any(
        question in record["message"]["content"]
        for record in payload["messages"][8:12]
    )


@pytest.mark.parametrize(
    ("message_id", "selected_text"),
    [
        (str(uuid4()), "not a real target"),
        (None, "not present in the target message"),
    ],
)
def test_invalid_challenge_does_not_advance_the_session(
    monkeypatch: pytest.MonkeyPatch,
    message_id: str | None,
    selected_text: str,
) -> None:
    first_round = create_round_one(monkeypatch)
    session_id = first_round["session"]["id"]
    target_id = message_id or first_round["messages"][0]["message"]["id"]

    response = client.post(
        f"/debates/{session_id}/interventions",
        headers={"X-User-Id": "preview-user"},
        json={
            "selected_message_id": target_id,
            "selected_text": selected_text,
            "question": "Please reconsider this point.",
        },
    )

    assert response.status_code == 409
    detail = client.get(
        f"/debates/{session_id}",
        headers={"X-User-Id": "preview-user"},
    ).json()
    assert detail["session"]["status"] == "awaiting_user"
    assert len(detail["messages"]) == 7


def test_enabled_preview_does_not_change_legacy_analysis_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)

    response = client.post(
        "/analysis/GOOG",
        headers={"X-User-Id": "legacy-user"},
        json={"question": "What is the cached context?"},
    )

    assert response.status_code == 201
    assert response.json()["ticker"] == "GOOG"
    assert client.get("/analysis", headers={"X-User-Id": "legacy-user"}).status_code == 200
