from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import pytest
from fastapi.testclient import TestClient

from app import main
from app.domain.debate import DebateDraftCheckpoint
from app.domain.explanations import ExplanationDraft
from app.providers.current_factors import build_current_factor_registry
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.repositories.memory_debate_repository import InMemoryDebateRepository
from app.services.analysis import AnalysisService
from app.services.cache import LocalCacheBackend, ResilientCacheBackend
from app.services.debate_admission import DebateAdmissionPolicy, DebateIdempotencyGuard
from app.services.debate_event_broker import InMemoryDebateEventBroker
from app.services.debate_preview import DebatePreviewService
from app.services.debate_snapshot_cache import StandardDebateSnapshotCache
from app.services.debate_state import transition_session
from app.services.debate_worker import DebateWorker
from app.services.demo_store import DemoStore
from app.services.explanation_admission import ExplanationAdmissionPolicy
from app.services.response_cache import JsonResponseCache
from test_cache_backend import BrokenBackend
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
    coordination_backend = ResilientCacheBackend(LocalCacheBackend())
    monkeypatch.setattr(
        main,
        "debate_admission_policy",
        DebateAdmissionPolicy(
            coordination_backend,
            rate_limit=3,
            rate_window_seconds=3600,
            active_ttl_seconds=1200,
        ),
    )
    monkeypatch.setattr(
        main,
        "debate_idempotency_guard",
        DebateIdempotencyGuard(coordination_backend, ttl_seconds=120),
    )
    monkeypatch.setattr(
        main,
        "explanation_admission_policy",
        ExplanationAdmissionPolicy(
            coordination_backend,
            rate_limit=12,
            rate_window_seconds=3600,
        ),
    )
    monkeypatch.setattr(main.settings, "auth_mode", "demo")
    monkeypatch.setattr(main.settings, "debate_workflow_v2", False)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", False)


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
    assert client.post(
        f"/debates/{uuid4()}/explanations",
        json={
            "message_id": str(uuid4()),
            "selected_text": "frozen snapshot",
            "question": "What does this mean here?",
        },
    ).status_code == 404
    assert "/debates" not in client.get("/openapi.json").json()["paths"]
    assert (
        "/debates/{session_id}/explanations"
        not in client.get("/openapi.json").json()["paths"]
    )

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
    explanation = client.post(
        f"/debates/{uuid4()}/explanations",
        json={
            "message_id": str(uuid4()),
            "selected_text": "frozen snapshot",
            "question": "What does this mean here?",
        },
    )
    assert explanation.status_code == 404
    assert explanation.json() == {"detail": "Debate V2 is not enabled"}


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
    assert all(record["presentation"] is not None for record in messages)
    assert all(
        record["presentation"]["argument"] == record["message"]["content"]
        for record in messages
    )
    assert all(
        len(record["presentation"]["facts_used"]) == len(record["citations"])
        for record in messages
    )
    assert all(
        fact["fact"]
        for record in messages
        for fact in record["presentation"]["facts_used"]
    )

    session_id = session["id"]
    headers = {"X-User-Id": "preview-user"}
    assert client.get("/debates", headers=headers).json()[0]["id"] == session_id
    assert client.get(f"/debates/{session_id}", headers=headers).json() == {
        "session": session,
        "messages": messages,
        "job": None,
        "execution_mode": "synchronous_preview",
    }
    assert len(client.get(f"/debates/{session_id}/messages", headers=headers).json()) == 7


def test_explanation_endpoint_returns_a_bounded_read_only_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = create_round_one(monkeypatch)
    session = payload["session"]
    target = payload["messages"][0]
    message = target["message"]
    session_id = UUID(session["id"])
    job_id = UUID(payload["job_id"])
    user_id = uuid5(NAMESPACE_URL, "ai-bull-vs-bear:user:preview-user")
    assert main.debate_preview_service is not None
    repository = main.debate_preview_service.repository
    session_before = repository.get_session(session_id, user_id)
    job_before = repository.get_job(job_id)
    messages_before = repository.list_messages(
        session_id,
        user_id,
        branch_id=session_before.active_branch_id,
    )

    response = client.post(
        f"/debates/{session_id}/explanations",
        headers={"X-User-Id": "preview-user"},
        json={
            "message_id": message["id"],
            "selected_text": "frozen snapshot",
            "question": "What does this mean here?",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["session_id"] == session["id"]
    assert result["source_message_id"] == message["id"]
    assert result["selected_text"] == "frozen snapshot"
    assert result["question"] == "What does this mean here?"
    assert result["provider_name"] == "deterministic-explainer"
    assert result["provider_version"] == "v1"
    assert result["guardrail_status"] == "passed"
    assert set(result["evidence_ids"]) <= {
        citation["evidence_id"] for citation in target["citations"]
    }
    assert repository.get_session(session_id, user_id) == session_before
    assert repository.get_job(job_id) == job_before
    assert repository.list_messages(
        session_id,
        user_id,
        branch_id=session_before.active_branch_id,
    ) == messages_before


def test_explanation_endpoint_accepts_a_frozen_interrupted_prefix_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    user_id = uuid5(NAMESPACE_URL, "ai-bull-vs-bear:user:preview-user")
    queued, job = build_queued_round_one()
    queued = queued.model_copy(update={"user_id": user_id})
    job = job.model_copy(update={"user_id": user_id})
    assert main.debate_preview_service is not None
    repository = main.debate_preview_service.repository
    repository.create_session_with_job(queued, job)
    running = transition_session(
        queued,
        "running_round_1",
        at=queued.updated_at + timedelta(seconds=1),
    )
    repository.update_session(running, expected_status="queued_round_1")
    checkpoint = DebateDraftCheckpoint(
        message_id=uuid4(),
        session_id=running.id,
        branch_id=running.active_branch_id,
        generation_id=running.active_generation_id,
        sequence_number=1,
        round_number=1,
        exchange_number=1,
        role="bull",
        message_kind="argument",
        content="Visible interrupted prefix with a possible unfinished conclusion",
        created_at=running.updated_at,
    )
    repository.checkpoint_draft(checkpoint)
    stopped = repository.interrupt_generation(
        running.id,
        running.user_id,
        running.active_generation_id,
        checkpoint.message_id,
        "Visible interrupted prefix",
        running.updated_at + timedelta(seconds=1),
    )
    job_before = repository.get_job(job.id)
    messages_before = repository.list_messages(
        stopped.id,
        stopped.user_id,
        branch_id=stopped.active_branch_id,
    )

    response = client.post(
        f"/debates/{stopped.id}/explanations",
        headers={"X-User-Id": "preview-user"},
        json={
            "message_id": str(checkpoint.message_id),
            "selected_text": "interrupted prefix",
            "question": "What can this unfinished point mean?",
        },
    )

    assert response.status_code == 200
    assert response.json()["evidence_ids"] == []
    assert "interrupted Bull prefix" in response.json()["content"]
    assert repository.get_session(stopped.id, stopped.user_id) == stopped
    assert repository.get_job(job.id) == job_before
    assert repository.list_messages(
        stopped.id,
        stopped.user_id,
        branch_id=stopped.active_branch_id,
    ) == messages_before


def test_explanation_endpoint_hides_ownership_and_selection_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = create_round_one(monkeypatch)
    session_id = payload["session"]["id"]
    message_id = payload["messages"][0]["message"]["id"]
    request = {
        "message_id": message_id,
        "selected_text": "frozen snapshot",
        "question": "What does this mean here?",
    }

    missing = client.post(
        f"/debates/{session_id}/explanations",
        headers={"X-User-Id": "another-user"},
        json=request,
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Debate explanation source was not found"}

    invalid = client.post(
        f"/debates/{session_id}/explanations",
        headers={"X-User-Id": "preview-user"},
        json={**request, "selected_text": "not in the source message"},
    )
    assert invalid.status_code == 409
    assert invalid.json() == {
        "detail": "Explanation request is not valid for this Debate message"
    }


def test_explanation_endpoint_hides_provider_failure_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingExplanationProvider:
        name = "failing-explainer"
        version = "test"

        def close(self) -> None:
            pass

        def generate_explanation(self, _request):
            raise RuntimeError("private provider response and request identifier")

    payload = create_round_one(monkeypatch)
    monkeypatch.setattr(
        main,
        "build_explanation_provider",
        lambda _settings: FailingExplanationProvider(),
    )
    response = client.post(
        f"/debates/{payload['session']['id']}/explanations",
        headers={"X-User-Id": "preview-user"},
        json={
            "message_id": payload["messages"][0]["message"]["id"],
            "selected_text": "frozen snapshot",
            "question": "What does this mean here?",
        },
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Explanation service is temporarily unavailable"}
    assert "private provider" not in response.text


@pytest.mark.parametrize(
    ("selected_text", "provider_fails", "expected_status"),
    [
        ("frozen snapshot", False, 200),
        ("text that is not present", False, 409),
        ("frozen snapshot", True, 503),
    ],
)
def test_explanation_endpoint_closes_provider_on_every_outcome(
    monkeypatch: pytest.MonkeyPatch,
    selected_text: str,
    provider_fails: bool,
    expected_status: int,
) -> None:
    class ClosingProvider:
        name = "closing-explainer"
        version = "test"

        def __init__(self) -> None:
            self.close_calls = 0

        def generate_explanation(self, _request):
            if provider_fails:
                raise RuntimeError("private provider response")
            return ExplanationDraft(content="A bounded explanation.")

        def close(self) -> None:
            self.close_calls += 1

    payload = create_round_one(monkeypatch)
    provider = ClosingProvider()
    monkeypatch.setattr(main, "build_explanation_provider", lambda _settings: provider)
    response = client.post(
        f"/debates/{payload['session']['id']}/explanations",
        headers={"X-User-Id": "preview-user"},
        json={
            "message_id": payload["messages"][0]["message"]["id"],
            "selected_text": selected_text,
            "question": "What does this mean here?",
        },
    )

    assert response.status_code == expected_status
    assert provider.close_calls == 1


def test_explanation_endpoint_returns_admission_headers_and_a_bounded_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = create_round_one(monkeypatch)
    policy = ExplanationAdmissionPolicy(
        ResilientCacheBackend(LocalCacheBackend()),
        rate_limit=2,
        rate_window_seconds=3600,
        clock=lambda: 3700.0,
    )
    monkeypatch.setattr(main, "explanation_admission_policy", policy)
    request = {
        "message_id": payload["messages"][0]["message"]["id"],
        "selected_text": "frozen snapshot",
        "question": "What does this mean here?",
    }
    headers = {"X-User-Id": "preview-user"}

    first = client.post(
        f"/debates/{payload['session']['id']}/explanations",
        headers=headers,
        json=request,
    )
    second = client.post(
        f"/debates/{payload['session']['id']}/explanations",
        headers=headers,
        json=request,
    )
    limited = client.post(
        f"/debates/{payload['session']['id']}/explanations",
        headers=headers,
        json=request,
    )

    assert first.status_code == second.status_code == 200
    assert first.headers["x-ratelimit-limit"] == "2"
    assert first.headers["x-ratelimit-remaining"] == "1"
    assert second.headers["x-ratelimit-remaining"] == "0"
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3500"
    assert limited.json() == {"detail": "Explanation request limit reached; retry later"}


def test_explanation_admission_degrades_to_local_cache_during_redis_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = create_round_one(monkeypatch)
    fallback = LocalCacheBackend()
    backend = ResilientCacheBackend(BrokenBackend(), fallback=fallback)
    policy = ExplanationAdmissionPolicy(
        backend,
        rate_limit=2,
        rate_window_seconds=3600,
        clock=lambda: 3700.0,
    )
    monkeypatch.setattr(main, "cache_backend", backend)
    monkeypatch.setattr(main, "explanation_admission_policy", policy)
    response = client.post(
        f"/debates/{payload['session']['id']}/explanations",
        headers={"X-User-Id": "preview-user"},
        json={
            "message_id": payload["messages"][0]["message"]["id"],
            "selected_text": "frozen snapshot",
            "question": "What does this mean here?",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-ratelimit-remaining"] == "1"
    assert backend.health().mode == "degraded"


def test_one_active_debate_is_enforced_before_new_factor_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    headers = {"X-User-Id": "single-active-user"}
    original_context = main._debate_context
    context_calls = 0

    def counting_context(ticker: str, question: str | None):
        nonlocal context_calls
        context_calls += 1
        return original_context(ticker, question)

    monkeypatch.setattr(main, "_debate_context", counting_context)

    first = client.post(
        "/debates",
        headers=headers,
        json={"ticker": "AAPL"},
    )
    second = client.post(
        "/debates",
        headers=headers,
        json={"ticker": "GOOG"},
    )

    assert first.status_code == 201
    assert first.headers["x-ratelimit-limit"] == "3"
    assert first.headers["x-ratelimit-remaining"] == "2"
    assert second.status_code == 409
    assert context_calls == 1
    assert second.json() == {
        "detail": "Finish or cancel the active Debate before starting another"
    }


def test_debate_rate_limit_allows_terminal_sessions_then_returns_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(
        main,
        "debate_admission_policy",
        DebateAdmissionPolicy(
            ResilientCacheBackend(LocalCacheBackend()),
            rate_limit=2,
            rate_window_seconds=3600,
            active_ttl_seconds=1200,
            clock=lambda: 3700.0,
        ),
    )
    headers = {"X-User-Id": "rate-limited-user"}

    for ticker in ("AAPL", "GOOG"):
        created = client.post(
            "/debates",
            headers=headers,
            json={"ticker": ticker},
        )
        assert created.status_code == 201
        session = created.json()["session"]
        cancelled = client.post(
            f"/debates/{session['id']}/cancel",
            headers=headers,
            json={"generation_id": session["active_generation_id"]},
        )
        assert cancelled.status_code == 202
        assert cancelled.json()["session"]["status"] == "cancelled"

    limited = client.post(
        "/debates",
        headers=headers,
        json={"ticker": "NVDA"},
    )

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3500"
    assert limited.json() == {
        "detail": "Debate generation limit reached; retry later"
    }


def test_standard_debate_does_not_reuse_a_prior_capture_across_users(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    registry = build_current_factor_registry()
    original_collect = registry.collect
    collect_calls = 0

    def counting_collect(context):
        nonlocal collect_calls
        collect_calls += 1
        return original_collect(context)

    cache = JsonResponseCache(
        ResilientCacheBackend(LocalCacheBackend()),
        enabled=True,
    )
    monkeypatch.setattr(registry, "collect", counting_collect)
    monkeypatch.setattr(main, "build_current_factor_registry", lambda: registry)
    monkeypatch.setattr(
        main,
        "debate_snapshot_cache",
        StandardDebateSnapshotCache(cache),
    )

    first = client.post(
        "/debates",
        headers={"X-User-Id": "standard-cache-user-a"},
        json={"ticker": "AAPL", "opening_side": "bull"},
    )
    second = client.post(
        "/debates",
        headers={"X-User-Id": "standard-cache-user-b"},
        json={"ticker": "AAPL", "opening_side": "bull"},
    )

    assert first.status_code == second.status_code == 201
    assert first.headers["x-cache-status"] == "MISS"
    assert second.headers["x-cache-status"] == "MISS"
    assert collect_calls == 2
    assert first.json()["session"]["user_id"] != second.json()["session"]["user_id"]
    assert first.json()["session"]["id"] != second.json()["session"]["id"]
    assert first.json()["messages"][0]["message"]["id"] != (
        second.json()["messages"][0]["message"]["id"]
    )


def test_custom_debate_question_bypasses_shared_snapshot_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    registry = build_current_factor_registry()
    original_collect = registry.collect
    collect_calls = 0

    def counting_collect(context):
        nonlocal collect_calls
        collect_calls += 1
        return original_collect(context)

    cache = JsonResponseCache(
        ResilientCacheBackend(LocalCacheBackend()),
        enabled=True,
    )
    monkeypatch.setattr(registry, "collect", counting_collect)
    monkeypatch.setattr(main, "build_current_factor_registry", lambda: registry)
    monkeypatch.setattr(
        main,
        "debate_snapshot_cache",
        StandardDebateSnapshotCache(cache),
    )
    request = {
        "ticker": "AAPL",
        "question": "My private scenario question",
        "opening_side": "bull",
    }

    first = client.post(
        "/debates",
        headers={"X-User-Id": "custom-cache-user-a"},
        json=request,
    )
    second = client.post(
        "/debates",
        headers={"X-User-Id": "custom-cache-user-b"},
        json=request,
    )

    assert first.status_code == second.status_code == 201
    assert first.headers["x-cache-status"] == "BYPASS"
    assert second.headers["x-cache-status"] == "BYPASS"
    assert collect_calls == 2
    assert cache.metrics.snapshot()["HIT"] == 0


def test_queued_create_returns_before_worker_and_is_http_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    admission_backend = LocalCacheBackend()
    coordination_backend = ResilientCacheBackend(admission_backend)
    admission_policy = DebateAdmissionPolicy(
        coordination_backend,
        rate_limit=3,
        rate_window_seconds=3600,
        active_ttl_seconds=1200,
        clock=lambda: 3700.0,
    )
    idempotency_guard = DebateIdempotencyGuard(
        coordination_backend,
        ttl_seconds=120,
    )
    monkeypatch.setattr(main, "debate_admission_policy", admission_policy)
    monkeypatch.setattr(main, "debate_idempotency_guard", idempotency_guard)
    request = {
        "ticker": "AAPL",
        "question": "Which dated factors support each side?",
        "opening_side": "bull",
        "idempotency_key": "classroom_demo_001",
    }
    headers = {"X-User-Id": "queue-owner"}

    first = client.post("/debates", headers=headers, json=request)
    repeated = client.post("/debates", headers=headers, json=request)

    assert first.status_code == 202
    assert repeated.status_code == 202
    assert repeated.json() == first.json()
    assert first.json()["execution_mode"] == "queued"
    assert first.json()["job"]["status"] == "queued"
    assert first.json()["session"]["status"] == "queued_round_1"
    assert first.json()["messages"] == []
    admitted_user_id = UUID(first.json()["session"]["user_id"])
    assert admission_backend.get(admission_policy.rate_key(admitted_user_id, 1)) == "1"
    assert (
        admission_backend.get(
            idempotency_guard.lock_key(admitted_user_id, request["idempotency_key"])
        )
        is None
    )
    assert main.debate_preview_service is not None
    repository = main.debate_preview_service.repository
    admitted_job = repository.get_job(UUID(first.json()["job_id"]))
    assert admitted_job is not None and admitted_job.queue_message_id == 1
    assert [
        event.type
        for event in main.debate_event_broker.replay(
            UUID(first.json()["session"]["id"])
        )
    ] == ["session.created", "job.queued"]

    worker = DebateWorker(
        repository,
        repository,  # type: ignore[arg-type]
        main.debate_preview_service.orchestrator,
    )
    result = asyncio.run(worker.run_once())
    completed = client.get(
        f"/debates/{first.json()['session']['id']}",
        headers=headers,
    )

    assert result.outcome == "completed"
    assert completed.status_code == 200
    assert completed.json()["session"]["status"] == "awaiting_user"
    assert len(completed.json()["messages"]) == 7


def test_queued_job_detail_exposes_configured_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    repository = InMemoryDebateRepository()
    provider = DeterministicDebateProvider()
    service = DebatePreviewService(
        repository,
        provider,
        provider,
        max_attempts=1,
    )
    monkeypatch.setattr(main, "debate_preview_service", service)

    response = client.post(
        "/debates",
        headers={"X-User-Id": "bounded-attempt-owner"},
        json={
            "ticker": "AAPL",
            "idempotency_key": "bounded_attempts_001",
        },
    )

    assert response.status_code == 202
    assert response.json()["job"]["max_attempts"] == 1


def test_queued_create_returns_retryable_conflict_while_idempotency_lock_is_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    user = "queue-lock-owner"
    user_id = uuid5(NAMESPACE_URL, f"ai-bull-vs-bear:user:{user}")
    idempotency_key = "classroom_demo_locked"
    held = main.debate_idempotency_guard.acquire(user_id, idempotency_key)
    original_context = main._debate_context
    context_calls = 0

    def counting_context(ticker: str, question: str | None):
        nonlocal context_calls
        context_calls += 1
        return original_context(ticker, question)

    monkeypatch.setattr(main, "_debate_context", counting_context)
    try:
        response = client.post(
            "/debates",
            headers={"X-User-Id": user},
            json={"ticker": "AAPL", "idempotency_key": idempotency_key},
        )
    finally:
        main.debate_idempotency_guard.release(held)

    assert response.status_code == 409
    assert response.headers["retry-after"] == "1"
    assert response.json() == {
        "detail": "An equivalent Debate request is being admitted; retry shortly"
    }
    assert context_calls == 0


def test_queued_create_releases_idempotency_lock_after_context_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    user = "queue-failed-owner"
    user_id = uuid5(NAMESPACE_URL, f"ai-bull-vs-bear:user:{user}")
    idempotency_key = "classroom_demo_failed"

    def fail_context(_ticker: str, _question: str | None):
        raise ValueError("simulated context failure")

    monkeypatch.setattr(main, "_debate_context", fail_context)
    response = client.post(
        "/debates",
        headers={"X-User-Id": user},
        json={"ticker": "AAPL", "idempotency_key": idempotency_key},
    )
    recovered = main.debate_idempotency_guard.acquire(user_id, idempotency_key)
    main.debate_idempotency_guard.release(recovered)

    assert response.status_code == 404


def test_queued_create_remains_idempotent_during_redis_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    fallback = LocalCacheBackend()
    backend = ResilientCacheBackend(BrokenBackend(), fallback=fallback)
    admission_policy = DebateAdmissionPolicy(
        backend,
        rate_limit=3,
        rate_window_seconds=3600,
        active_ttl_seconds=1200,
        clock=lambda: 3700.0,
    )
    monkeypatch.setattr(main, "cache_backend", backend)
    monkeypatch.setattr(main, "debate_admission_policy", admission_policy)
    monkeypatch.setattr(
        main,
        "debate_idempotency_guard",
        DebateIdempotencyGuard(backend, ttl_seconds=120),
    )
    request = {
        "ticker": "AAPL",
        "question": "Which bounded factors remain during an outage?",
        "idempotency_key": "classroom_redis_outage",
    }
    headers = {"X-User-Id": "queue-outage-owner"}

    first = client.post("/debates", headers=headers, json=request)
    repeated = client.post("/debates", headers=headers, json=request)
    health = client.get("/health/cache", params={"probe": "true"})

    assert first.status_code == repeated.status_code == 202
    assert repeated.json() == first.json()
    user_id = UUID(first.json()["session"]["user_id"])
    assert fallback.get(admission_policy.rate_key(user_id, 1)) == "1"
    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["redis_reachable"] is False
    assert health.json()["degraded_operations"] >= 9


def test_queued_create_rejects_reusing_key_for_different_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    headers = {"X-User-Id": "queue-owner"}
    base = {
        "ticker": "AAPL",
        "question": "First bounded question?",
        "idempotency_key": "classroom_demo_002",
    }
    assert client.post("/debates", headers=headers, json=base).status_code == 202

    conflict = client.post(
        "/debates",
        headers=headers,
        json={**base, "question": "A different request with the same key?"},
    )

    assert conflict.status_code == 409


def test_queued_round_two_returns_before_worker_and_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    headers = {"X-User-Id": "queue-round-two-owner"}
    first = client.post(
        "/debates",
        headers=headers,
        json={
            "ticker": "AAPL",
            "question": "Which evidence supports each side?",
            "idempotency_key": "round_two_setup_001",
        },
    )
    assert first.status_code == 202
    assert main.debate_preview_service is not None
    repository = main.debate_preview_service.repository
    worker = DebateWorker(
        repository,
        repository,  # type: ignore[arg-type]
        main.debate_preview_service.orchestrator,
    )
    assert asyncio.run(worker.run_once()).outcome == "completed"
    awaiting = client.get(
        f"/debates/{first.json()['session']['id']}",
        headers=headers,
    ).json()
    target = awaiting["messages"][1]["message"]
    request = {
        "selected_message_id": target["id"],
        "selected_text": target["content"][:40],
        "question": "Does this rebuttal underweight the filing evidence?",
        "idempotency_key": "round_two_challenge_001",
    }

    queued = client.post(
        f"/debates/{first.json()['session']['id']}/interventions",
        headers=headers,
        json=request,
    )
    repeated = client.post(
        f"/debates/{first.json()['session']['id']}/interventions",
        headers=headers,
        json=request,
    )

    assert queued.status_code == repeated.status_code == 202
    assert repeated.json() == queued.json()
    assert queued.json()["execution_mode"] == "queued"
    assert queued.json()["job"]["status"] == "queued"
    assert queued.json()["session"]["status"] == "queued_round_2"
    assert len(queued.json()["messages"]) == 8
    assert queued.json()["messages"][-1]["message"]["role"] == "user"
    round_two_job = repository.get_job(UUID(queued.json()["job_id"]))
    assert round_two_job is not None and round_two_job.queue_message_id == 2

    assert asyncio.run(worker.run_once()).outcome == "completed"
    completed = client.get(
        f"/debates/{first.json()['session']['id']}",
        headers=headers,
    )
    assert completed.status_code == 200
    assert completed.json()["execution_mode"] == "queued"
    assert completed.json()["session"]["status"] == "completed"
    assert len(completed.json()["messages"]) == 13


def test_queued_round_two_rejects_conflicting_idempotency_reuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    headers = {"X-User-Id": "queue-round-two-conflict"}
    first = client.post(
        "/debates",
        headers=headers,
        json={
            "ticker": "AAPL",
            "idempotency_key": "round_two_setup_002",
        },
    )
    assert main.debate_preview_service is not None
    repository = main.debate_preview_service.repository
    worker = DebateWorker(
        repository,
        repository,  # type: ignore[arg-type]
        main.debate_preview_service.orchestrator,
    )
    assert asyncio.run(worker.run_once()).outcome == "completed"
    awaiting = client.get(
        f"/debates/{first.json()['session']['id']}",
        headers=headers,
    ).json()
    target = awaiting["messages"][0]["message"]
    request = {
        "selected_message_id": target["id"],
        "selected_text": target["content"][:40],
        "question": "First bounded challenge?",
        "idempotency_key": "round_two_challenge_002",
    }
    path = f"/debates/{first.json()['session']['id']}/interventions"
    assert client.post(path, headers=headers, json=request).status_code == 202

    conflict = client.post(
        path,
        headers=headers,
        json={**request, "question": "A different bounded challenge?"},
    )

    assert conflict.status_code == 409


def test_queue_enabled_app_lifespan_starts_and_stops_configured_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_preview(monkeypatch)
    monkeypatch.setattr(main.settings, "debate_queue_enabled", True)
    monkeypatch.setattr(main.settings, "debate_worker_concurrency", 2)
    lifecycle_events: list[str] = []

    class FakeWorker:
        async def run_forever(
            self,
            stop_event: asyncio.Event,
            *,
            poll_seconds: float,
        ) -> None:
            lifecycle_events.append(f"started:{poll_seconds}")
            try:
                await stop_event.wait()
            finally:
                lifecycle_events.append("stopped")

    monkeypatch.setattr(main, "build_configured_debate_worker", FakeWorker)

    with TestClient(main.app) as lifecycle_client:
        assert lifecycle_client.get("/health").status_code == 200
        assert len([event for event in lifecycle_events if event.startswith("started:")]) == 2

    assert lifecycle_events.count("stopped") == 2


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


def test_round_two_stream_skips_replayed_round_one_terminal_event() -> None:
    queued, _ = build_queued_round_one()
    round_two_generation = uuid4()
    round_two = queued.model_copy(update={
        "active_generation_id": round_two_generation,
        "status": "running_round_2",
    })
    main.debate_event_broker.publish(
        queued.id,
        "session.awaiting_user",
        payload={"generation_id": str(queued.active_generation_id), "status": "awaiting_user"},
    )
    main.debate_event_broker.publish(
        queued.id,
        "job.queued",
        payload={"generation_id": str(round_two_generation)},
    )
    main.debate_event_broker.publish(
        queued.id,
        "session.completed",
        payload={"generation_id": str(round_two_generation), "status": "completed"},
    )

    frames = list(main._debate_sse_frames(
        round_two,
        after_sequence=0,
        initial_events=main.debate_event_broker.replay(queued.id),
        heartbeat_seconds=0,
    ))

    assert len(frames) == 3
    assert "event: session.awaiting_user" in frames[0]
    assert "event: job.queued" in frames[1]
    assert "event: session.completed" in frames[2]


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


def test_live_snapshot_quote_is_separate_and_missing_provenance_fails(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from fastapi import HTTPException
    from app.schemas import MarketQuote
    from app.services.debate_snapshot_provenance import completed_close_cutoff

    now = datetime.now(timezone.utc)
    end = completed_close_cutoff(now)
    prices = [dict(date=(end - timedelta(days=49-i)).isoformat(), open=100,
                   high=102, low=99, close=101, volume=100,
                   source="daily_market_cache", is_stale=False) for i in range(50)]
    monkeypatch.setattr(main.settings, "app_data_mode", "standard")
    monkeypatch.setattr(main.settings, "debate_streaming_provider", "groq")
    monkeypatch.setattr(main.store, "get_prices", lambda ticker: prices)
    from app.services.macro_data import DEFAULT_MACRO_SERIES
    definitions = {item.code: item for item in DEFAULT_MACRO_SERIES}
    series_rows = [dict(code=item.code, name=item.name, source=item.source,
                        unit=item.unit, frequency=item.frequency) for item in definitions.values()]
    monkeypatch.setattr(main.store, "get_macro_series", lambda: series_rows)
    monkeypatch.setattr(main.store, "get_macro_observations", lambda code, limit: [dict(
        series_code=code, observation_date=end.isoformat(), value=1,
        retrieved_at=now.isoformat(), metadata={"provider": definitions[code].source,
        "provider_series_id": definitions[code].provider_series_id})])
    evidence = [dict(id=kind, ticker="AAPL", source_type=kind,
                     title="Current document", excerpt="Source observation",
                     url="https://example.com/document", published_at=now.isoformat(),
                     metadata={"storage": "supabase", "document_id": kind})
                for kind in ("news", "filing")]
    monkeypatch.setattr(main.store, "get_evidence", lambda ticker: evidence)
    from test_debate_financial_admission import fact
    monkeypatch.setattr(main.store, "get_financial_facts", lambda ticker: [fact(
        period_start=(now-timedelta(days=90)).date().isoformat(),
        period_end=(now-timedelta(days=30)).date().isoformat(),
        filed_at=(now-timedelta(days=5)).date().isoformat())])
    quote = MarketQuote(ticker="AAPL", close=105, open=104, high=106, low=103,
                        previous_close=101, as_of=(now-timedelta(seconds=5)).isoformat(),
                        retrieved_at=now.isoformat(), source="finnhub_quote")
    monkeypatch.setattr(main, "get_quote", lambda ticker: quote)
    context, factors, _ = main._debate_context("AAPL", None)
    assert context.prices[-1].close == 101
    assert context.market_quote.close == 105
    assert context.market_quote.retrieved_at == now
    assert context.captured_at >= now
    assert any(item.factor_key == "market.latest-provider-quote" for item in factors.observations)
    assert context.allowed_evidence_ids == {"news", "filing"}
    assert len(context.financial_facts) == 1
    assert len(context.macro_context) == 7
    monkeypatch.setattr(main.store, "get_macro_series", lambda: [])
    with pytest.raises(HTTPException) as no_macro:
        main._debate_context("AAPL", None)
    assert no_macro.value.status_code == 409
    monkeypatch.setattr(main.store, "get_macro_series", lambda: series_rows)
    monkeypatch.setattr(main.store, "get_evidence", lambda ticker: [])
    with pytest.raises(HTTPException) as missing:
        main._debate_context("AAPL", None)
    assert missing.value.status_code == 409
    monkeypatch.setattr(main.store, "get_evidence", lambda ticker: evidence)
    quote.retrieved_at = None
    with pytest.raises(HTTPException) as error:
        main._debate_context("AAPL", None)
    assert error.value.status_code == 409


def test_interrupt_endpoint_freezes_prefix_and_rejects_invalid_requests(monkeypatch):
    first = create_round_one(monkeypatch, user='interrupt-owner')
    session = first['session']
    target = first['messages'][0]['message']
    endpoint = f"/debates/{session['id']}/interrupt"
    headers = {'X-User-Id': 'interrupt-owner'}
    payload = {'generation_id': session['active_generation_id'], 'message_id': target['id'],
               'visible_prefix': target['content'][:8]}
    monkeypatch.setattr(main.settings, 'debate_interruptions_enabled', False)
    assert client.post(endpoint, headers=headers, json=payload).status_code == 404
    monkeypatch.setattr(main.settings, 'debate_interruptions_enabled', True)
    assert client.post(endpoint, headers={'X-User-Id': 'other'}, json=payload).status_code == 404
    assert client.post(endpoint, headers=headers,
                       json={**payload, 'visible_prefix': 'invented prefix'}).status_code == 409
    stopped = client.post(endpoint, headers=headers, json=payload)
    assert stopped.status_code == 200
    assert stopped.json()['session']['status'] == 'interrupted_awaiting_user'
    assert stopped.json()['session']['completed_at'] is None
    records = stopped.json()['messages']
    assert len(records) == 1
    assert records[0]['message']['content'] == payload['visible_prefix']
    assert records[0]['message']['is_complete'] is False
    assert client.post(endpoint, headers=headers, json=payload).json() == stopped.json()


def test_interrupted_session_can_be_explicitly_ended(monkeypatch):
    first = create_round_one(monkeypatch, user='end-interruption-owner')
    monkeypatch.setattr(main.settings, 'debate_interruptions_enabled', True)
    session = first['session']
    headers = {'X-User-Id': 'end-interruption-owner'}
    stopped = client.post(f"/debates/{session['id']}/interrupt", headers=headers, json={
        'generation_id': session['active_generation_id'],
        'message_id': first['messages'][0]['message']['id'], 'visible_prefix': ''})
    assert stopped.status_code == 200
    ended = client.post(f"/debates/{session['id']}/cancel", headers=headers,
        json={'generation_id': stopped.json()['session']['active_generation_id']})
    assert ended.status_code == 202
    assert ended.json()['session']['status'] == 'cancelled'
    assert ended.json()['messages'][0]['message']['is_complete'] is False


def test_end_interruption_does_not_require_a_recorded_user_point(monkeypatch):
    first = create_round_one(monkeypatch, user='end-without-point-owner')
    monkeypatch.setattr(main.settings, 'debate_interruptions_enabled', True)
    headers = {'X-User-Id': 'end-without-point-owner'}
    target = first['messages'][0]['message']
    stopped = client.post(f"/debates/{first['session']['id']}/interrupt", headers=headers, json={
        'generation_id': first['session']['active_generation_id'],
        'message_id': target['id'], 'visible_prefix': ''})
    assert stopped.status_code == 200
    ended = client.post(f"/debates/{first['session']['id']}/end-interruption", headers=headers,
        json={'interrupted_message_id': target['id']})
    assert ended.status_code == 202
    assert ended.json()['session']['status'] == 'cancelled'
    assert ended.json()['messages'][0]['message']['is_complete'] is False


def test_before_output_stop_can_be_ended_without_an_interjection(monkeypatch):
    monkeypatch.setattr(main.settings, 'debate_queue_enabled', True)
    enable_preview(monkeypatch)
    response = client.post(
        "/debates",
        headers={'X-User-Id': 'end-before-output-owner'},
        json={
            'ticker': 'AAPL',
            'question': 'Which dated factors support each side?',
            'opening_side': 'bull',
        },
    )
    assert response.status_code == 202
    first = response.json()
    monkeypatch.setattr(main.settings, 'debate_interruptions_enabled', True)
    headers = {'X-User-Id': 'end-before-output-owner'}
    session = first['session']
    stopped = client.post(
        f"/debates/{session['id']}/interrupt-before-output",
        headers=headers,
        json={'generation_id': session['active_generation_id']},
    )
    assert stopped.status_code == 200
    target = stopped.json()['messages'][-1]['message']
    assert target['content'] == ''
    assert target['metadata'] == {'interrupted': True, 'before_output': True}

    ended = client.post(
        f"/debates/{session['id']}/end-interruption",
        headers=headers,
        json={'interrupted_message_id': target['id']},
    )
    assert ended.status_code == 202
    assert ended.json()['session']['status'] == 'cancelled'
    assert ended.json()['messages'][-1]['message']['id'] == target['id']


@pytest.mark.parametrize('round_number,stop_index', [(1, i) for i in range(7)] + [(2, i) for i in range(5)])
def test_interject_then_continue_resumes_only_unfinished_plan_slots(monkeypatch, round_number, stop_index):
    first = create_round_one(monkeypatch, user='continue-owner')
    if round_number == 2:
        initial_target = first['messages'][1]['message']
        response = client.post(f"/debates/{first['session']['id']}/interventions",
            headers={'X-User-Id': 'continue-owner'}, json={
                'selected_message_id': initial_target['id'],
                'selected_text': initial_target['content'][:40],
                'question': 'Does this underweight the filing risk?'})
        assert response.status_code == 201
        first = response.json()
    monkeypatch.setattr(main.settings, 'debate_interruptions_enabled', True)
    monkeypatch.setattr(main.settings, 'debate_queue_enabled', True)
    session = first['session']
    headers = {'X-User-Id': 'continue-owner'}
    round_messages = [r['message'] for r in first['messages']
                      if r['message']['round_number'] == round_number
                      and r['message']['role'] in {'bull', 'bear', 'judge'}]
    target = round_messages[stop_index]
    stopped = client.post(f"/debates/{session['id']}/interrupt", headers=headers, json={
        'generation_id': session['active_generation_id'], 'message_id': target['id'],
        'visible_prefix': target['content'][:8]})
    assert stopped.status_code == 200
    waiting_generation = stopped.json()['session']['active_generation_id']
    point_payload = {'generation_id': waiting_generation, 'content': 'Please consider the downside.',
                     'idempotency_key': 'point-continue-001'}
    point_response = client.post(f"/debates/{session['id']}/interjections", headers=headers, json=point_payload)
    assert point_response.status_code == 201
    assert point_response.json()['session']['status'] == 'interrupted_awaiting_user'
    assert point_response.json()['job'] is None
    assert client.post(f"/debates/{session['id']}/interjections", headers=headers, json=point_payload).json() == point_response.json()
    point = point_response.json()['messages'][-1]['message']
    continue_payload = {'generation_id': waiting_generation, 'interjection_id': point['id'],
                        'idempotency_key': 'continue-001'}
    continued = client.post(f"/debates/{session['id']}/continue", headers=headers, json=continue_payload)
    assert continued.status_code == 202
    result = continued.json()
    assert result['session']['status'] == f'queued_round_{round_number}'
    assert result['session']['active_generation_id'] != waiting_generation
    assert result['session']['analysis_context'] == session['analysis_context']
    assert client.post(f"/debates/{session['id']}/continue", headers=headers, json=continue_payload).json() == result
    assert main.debate_preview_service is not None
    finished = asyncio.run(main.debate_preview_service.orchestrator.execute_job_streaming(UUID(result['job']['id'])))
    assert finished.status == ('awaiting_user' if round_number == 1 else 'completed')
    repo = main.debate_preview_service.repository
    messages = repo.list_messages(finished.id, finished.user_id, branch_id=finished.active_branch_id)
    assert sum(m.is_complete and m.role in {'bull', 'bear', 'judge'} for m in messages) == (7 if round_number == 1 else 12)
    assert sum(not m.is_complete for m in messages) == 1
    job = repo.get_job(UUID(result['job']['id']))
    assert job.provider_request_count == (7 if round_number == 1 else 5) - stop_index


def test_end_interruption_cancels_a_concurrently_queued_continue(monkeypatch):
    first = create_round_one(monkeypatch, user='end-continue-owner')
    monkeypatch.setattr(main.settings, 'debate_interruptions_enabled', True)
    monkeypatch.setattr(main.settings, 'debate_queue_enabled', True)
    session = first['session']
    headers = {'X-User-Id': 'end-continue-owner'}
    target = first['messages'][0]['message']
    stopped = client.post(f"/debates/{session['id']}/interrupt", headers=headers, json={
        'generation_id': session['active_generation_id'], 'message_id': target['id'], 'visible_prefix': ''}).json()
    generation = stopped['session']['active_generation_id']
    point = client.post(f"/debates/{session['id']}/interjections", headers=headers, json={
        'generation_id': generation, 'content': 'Consider the risk.', 'idempotency_key': 'point-end-001'}).json()['messages'][-1]['message']
    continuation = {'generation_id': generation, 'interjection_id': point['id'], 'idempotency_key': 'continue-end-001'}
    assert client.post(f"/debates/{session['id']}/continue", headers=headers, json=continuation).status_code == 202
    ended = client.post(f"/debates/{session['id']}/end-interruption", headers=headers,
        json={'interrupted_message_id': target['id']})
    assert ended.status_code == 202
    assert ended.json()['session']['status'] == 'cancelled'
    replay = client.post(f"/debates/{session['id']}/continue", headers=headers, json=continuation)
    assert replay.json()['session']['status'] == 'cancelled'
