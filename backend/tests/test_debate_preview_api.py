from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app import main
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.analysis import AnalysisService
from app.services.debate_event_broker import InMemoryDebateEventBroker
from app.services.debate_preview import DebatePreviewService
from app.services.demo_store import DemoStore
from test_debate_orchestrator import build_queued_round_one


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    store = DemoStore()
    repository = InMemoryDebateRepository()
    provider = DeterministicDebateProvider()
    event_broker = InMemoryDebateEventBroker()
    service = DebatePreviewService(
        repository,
        provider,
        provider,
        event_publisher=event_broker,
    )
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "analysis_service", AnalysisService(store))
    monkeypatch.setattr(main, "debate_event_broker", event_broker)
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


def test_event_stream_replays_ordered_round_one_and_supports_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_round = create_round_one(monkeypatch)
    session_id = first_round["session"]["id"]
    headers = {"X-User-Id": "preview-user"}

    response = client.get(f"/debates/{session_id}/events", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-cache, no-transform"
    frames = [frame for frame in response.text.strip().split("\n\n") if frame]
    event_types = [
        next(line.removeprefix("event: ") for line in frame.splitlines() if line.startswith("event: "))
        for frame in frames
    ]
    event_ids = [
        int(next(line.removeprefix("id: ") for line in frame.splitlines() if line.startswith("id: ")))
        for frame in frames
    ]
    assert event_ids == list(range(1, len(event_ids) + 1))
    assert event_types[:3] == ["session.created", "job.queued", "job.started"]
    assert event_types[-1] == "session.awaiting_user"
    assert "turn.delta" in event_types
    assert "judge.completed" in event_types

    resume_cursor = event_ids[-3]
    resumed = client.get(
        f"/debates/{session_id}/events",
        headers={**headers, "Last-Event-ID": str(resume_cursor)},
    )
    resumed_ids = [
        int(line.removeprefix("id: "))
        for line in resumed.text.splitlines()
        if line.startswith("id: ")
    ]
    assert resumed.status_code == 200
    assert resumed_ids == event_ids[-2:]


def test_event_stream_is_owner_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    first_round = create_round_one(monkeypatch, user="stream-owner")
    session_id = first_round["session"]["id"]

    response = client.get(
        f"/debates/{session_id}/events",
        headers={"X-User-Id": "different-user"},
    )

    assert response.status_code == 404


def test_cancel_endpoint_is_owner_scoped_generation_safe_and_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_round = create_round_one(monkeypatch, user="cancel-owner")
    session = first_round["session"]
    session_id = session["id"]
    headers = {"X-User-Id": "cancel-owner"}

    wrong_owner = client.post(
        f"/debates/{session_id}/cancel",
        headers={"X-User-Id": "different-user"},
        json={"generation_id": session["active_generation_id"]},
    )
    assert wrong_owner.status_code == 404

    stale = client.post(
        f"/debates/{session_id}/cancel",
        headers=headers,
        json={"generation_id": str(uuid4())},
    )
    assert stale.status_code == 409
    assert "generation changed" in stale.json()["detail"]

    cancelled = client.post(
        f"/debates/{session_id}/cancel",
        headers=headers,
        json={"generation_id": session["active_generation_id"]},
    )
    repeated = client.post(
        f"/debates/{session_id}/cancel",
        headers=headers,
        json={"generation_id": session["active_generation_id"]},
    )

    assert cancelled.status_code == 202
    assert repeated.status_code == 202
    assert cancelled.json() == repeated.json()
    assert cancelled.json()["session"]["status"] == "cancelled"
    assert cancelled.json()["session"]["active_generation_id"] != session[
        "active_generation_id"
    ]
    assert len(cancelled.json()["messages"]) == 7


def test_running_event_stream_emits_an_unbuffered_heartbeat() -> None:
    queued, _ = build_queued_round_one()
    assert main.debate_preview_service is not None
    main.debate_preview_service.repository.create_session(queued)
    frames = main._debate_sse_frames(
        queued,
        after_sequence=0,
        heartbeat_seconds=0,
    )

    heartbeat = next(frames)
    frames.close()

    assert heartbeat.startswith("event: heartbeat\n")
    assert "id:" not in heartbeat
    assert '"latest_sequence":0' in heartbeat


def test_expired_event_cursor_requires_canonical_message_reload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = InMemoryDebateRepository()
    provider = DeterministicDebateProvider()
    event_broker = InMemoryDebateEventBroker(max_events_per_session=3)
    service = DebatePreviewService(
        repository,
        provider,
        provider,
        event_publisher=event_broker,
    )
    monkeypatch.setattr(main, "debate_event_broker", event_broker)
    monkeypatch.setattr(main, "debate_preview_service", service)
    first_round = create_round_one(monkeypatch)
    session_id = first_round["session"]["id"]

    response = client.get(
        f"/debates/{session_id}/events?after_sequence=0",
        headers={"X-User-Id": "preview-user"},
    )

    assert response.status_code == 409
    assert "reload canonical Debate messages" in response.json()["detail"]
    assert int(response.headers["X-Debate-Latest-Sequence"]) > 3


@pytest.mark.parametrize("last_event_id", ["not-a-sequence", "-1"])
def test_event_stream_rejects_invalid_last_event_id(
    monkeypatch: pytest.MonkeyPatch,
    last_event_id: str,
) -> None:
    first_round = create_round_one(monkeypatch)
    session_id = first_round["session"]["id"]

    response = client.get(
        f"/debates/{session_id}/events",
        headers={"X-User-Id": "preview-user", "Last-Event-ID": last_event_id},
    )

    assert response.status_code == 400


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
