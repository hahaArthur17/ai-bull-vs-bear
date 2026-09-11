from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest

from scripts.verify_current_sha_live_queue import (
    AcceptanceConfig,
    AuthenticatedApi,
    SseFrameParser,
    verify_current_sha_live_queue,
)


SESSION_ID = "10000000-0000-4000-8000-000000000901"
BRANCH_ID = "20000000-0000-4000-8000-000000000901"
GENERATION_ONE = "30000000-0000-4000-8000-000000000901"
GENERATION_TWO = "30000000-0000-4000-8000-000000000902"
SHA = "0123456789abcdef0123456789abcdef01234567"


def analysis_context() -> dict[str, Any]:
    start = date(2026, 6, 23)
    prices = [
        {
            "date": (start + timedelta(days=index)).isoformat(),
            "open": 200.0,
            "high": 202.0,
            "low": 199.0,
            "close": 201.0,
            "volume": 1_000_000,
            "source": "daily_market_cache",
            "is_stale": False,
        }
        for index in range(50)
    ]
    evidence = [
        {
            "id": "E1",
            "ticker": "AAPL",
            "source_type": "news",
            "title": "Current company update",
            "url": "https://example.test/news",
            "published_at": "2026-08-10T00:00:00Z",
            "excerpt": "Current company evidence.",
            "freshness": {"status": "current"},
        },
        {
            "id": "E2",
            "ticker": "AAPL",
            "source_type": "filing",
            "title": "Quarterly filing",
            "url": "https://www.sec.gov/Archives/example",
            "published_at": "2026-07-31T00:00:00Z",
            "excerpt": "Current filing evidence.",
            "freshness": {"status": "current"},
        },
    ]
    macro_codes = (
        "effective_fed_funds_rate",
        "sp500",
        "treasury_10y_yield",
        "treasury_2y_yield",
        "treasury_30y_yield",
        "vix",
        "wti_spot",
    )
    return {
        "ticker": "AAPL",
        "as_of": prices[-1]["date"],
        "captured_at": "2026-08-11T00:01:00Z",
        "latest_completed_close_date": prices[-1]["date"],
        "market_quote": {
            "ticker": "AAPL",
            "source": "finnhub_quote",
            "as_of": "2026-08-11T00:00:00Z",
            "retrieved_at": "2026-08-11T00:01:00Z",
            "freshness": {"status": "current"},
            "market_session": "after_hours",
        },
        "prices": prices,
        "evidence": evidence,
        "macro_context": [
            {
                "code": code,
                "observation_date": "2026-08-10",
                "retrieved_at": "2026-08-11T00:00:00Z",
            }
            for code in macro_codes
        ],
        "financial_facts": [{
            "form": "10-Q",
            "filed_at": "2026-07-31",
            "period_end": "2026-06-27",
        }],
        "allowed_evidence_ids": ["E1", "E2"],
    }


def event(sequence: int, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "event_id": str(uuid4()),
        "session_id": SESSION_ID,
        "sequence": sequence,
        "type": event_type,
        "timestamp": "2026-09-10T00:00:00Z",
        "payload": payload,
    }


def sse(events: list[dict[str, Any]]) -> str:
    return "".join(
        f"id: {item['sequence']}\n"
        f"event: {item['type']}\n"
        f"data: {json.dumps(item, separators=(',', ':'))}\n\n"
        for item in events
    )


def message(
    sequence: int,
    role: str,
    round_number: int,
    *,
    content: str | None = None,
    generation_id: str = GENERATION_ONE,
) -> dict[str, Any]:
    if content is None:
        content = f"{role.title()} evidence point {sequence} [E1]."
    return {
        "id": f"50000000-0000-4000-8000-{sequence:012d}",
        "session_id": SESSION_ID,
        "branch_id": BRANCH_ID,
        "generation_id": generation_id,
        "sequence_number": sequence,
        "round_number": round_number,
        "exchange_number": 0 if role == "judge" else ((sequence - 1) // 2) % 3 + 1,
        "role": role,
        "message_kind": "summary" if role == "judge" else ("argument" if sequence in {1, 9} else "rebuttal"),
        "content": content,
        "is_complete": True,
        "metadata": {
            "provider": "groq-live-debate" if role != "judge" else "groq-live-judge",
            "provider_version": "test-v1",
            "model_name": "openai/gpt-oss-20b",
            "stream_mode": "async_provider",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    }


def record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "message": item,
        "citations": [{
            "message_id": item["id"],
            "evidence_id": "E1",
            "citation_order": 1,
        }],
    }


def session(status: str, *, generation_id: str = GENERATION_ONE, interim: str | None = None, final: str | None = None) -> dict[str, Any]:
    return {
        "id": SESSION_ID,
        "user_id": "90000000-0000-4000-8000-000000000901",
        "stock_id": 1,
        "ticker": "AAPL",
        "mode": "demo",
        "status": status,
        "opening_side": "bull",
        "active_branch_id": BRANCH_ID,
        "active_generation_id": generation_id,
        "interim_judge_message_id": interim,
        "final_judge_message_id": final,
        "analysis_context": analysis_context(),
    }


def job(
    job_id: str,
    job_type: str,
    status: str = "queued",
    *,
    max_attempts: int = 3,
) -> dict[str, Any]:
    return {
        "id": job_id,
        "session_id": SESSION_ID,
        "user_id": "90000000-0000-4000-8000-000000000901",
        "job_type": job_type,
        "status": status,
        "max_attempts": max_attempts,
        "provider_request_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def fixture_transport(
    *,
    expose_sha_header: bool = True,
    include_r1_retry: bool = True,
    max_attempts: int = 3,
    fail_first_sse_connection: bool = False,
) -> tuple[httpx.MockTransport, dict[str, Any]]:
    r1_messages = [
        message(1, "bull", 1),
        message(2, "bear", 1),
        message(3, "bull", 1),
        message(4, "bear", 1),
        message(5, "bull", 1),
        message(6, "bear", 1),
        message(7, "judge", 1),
    ]
    challenge = message(8, "user", 2, content="Does this rebuttal underweight the filing risk?", generation_id=GENERATION_TWO)
    challenge["message_kind"] = "question"
    r2_messages = [
        message(9, "bull", 2, generation_id=GENERATION_TWO),
        message(10, "bear", 2, generation_id=GENERATION_TWO),
        message(11, "bull", 2, generation_id=GENERATION_TWO),
        message(12, "bear", 2, generation_id=GENERATION_TWO),
        message(13, "judge", 2, generation_id=GENERATION_TWO),
    ]
    all_messages = r1_messages + [challenge] + r2_messages
    r1_records = [record(item) for item in r1_messages]
    final_records = [record(item) for item in all_messages]
    initial_detail = {"session": session("queued_round_1"), "messages": [], "job": job("70000000-0000-4000-8000-000000000901", "round_1", max_attempts=max_attempts), "execution_mode": "queued"}
    r1_detail = {"session": session("awaiting_user", interim=r1_messages[-1]["id"]), "messages": r1_records, "job": None, "execution_mode": "queued"}
    challenge_detail = {"session": session("queued_round_2", generation_id=GENERATION_TWO, interim=r1_messages[-1]["id"]), "messages": r1_records + [record(challenge)], "job": job("70000000-0000-4000-8000-000000000902", "round_2", max_attempts=max_attempts), "execution_mode": "queued"}
    final_detail = {"session": session("completed", generation_id=GENERATION_TWO, interim=r1_messages[-1]["id"], final=r2_messages[-1]["id"]), "messages": final_records, "job": None, "execution_mode": "queued"}

    def attempts(
        items: list[dict[str, Any]],
        *,
        include_unknown: bool = False,
        id_offset: int = 0,
    ) -> list[dict[str, Any]]:
        rows = []
        for index, item in enumerate(items, start=1):
            rows.append({
                "id": f"80000000-0000-4000-8000-{index + id_offset:012d}",
                "session_id": SESSION_ID,
                "generation_id": item["generation_id"],
                "message_id": item["id"],
                "role": item["role"],
                "provider": item["metadata"]["provider"],
                "model": item["metadata"]["model_name"],
                "admitted_at": "2026-09-10T00:00:00Z",
                "dispatched_at": "2026-09-10T00:00:00Z",
                "finished_at": "2026-09-10T00:00:01Z",
                "outcome": "completed",
                "usage_status": "reported",
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            })
        # A failed provider request with no provider usage exercises the
        # unknown-use accounting path while retaining the same canonical slot.
        if include_unknown:
            unknown = dict(rows[1])
            unknown["id"] = "80000000-0000-4000-8000-000000000099"
            unknown["outcome"] = "failed"
            unknown["usage_status"] = "unknown"
            unknown["prompt_tokens"] = unknown["completion_tokens"] = unknown["total_tokens"] = None
            rows.insert(1, unknown)
        return rows

    r1_attempts = attempts(r1_messages, include_unknown=include_r1_retry)
    r2_attempts = attempts(r2_messages, id_offset=8)
    state = {"requests": [], "headers": [], "details": {"r1": r1_detail, "challenge": challenge_detail, "final": final_detail}, "r1_attempts": r1_attempts, "all_attempts": r1_attempts + r2_attempts, "fail_first_sse_connection": fail_first_sse_connection}
    r1_events = [
        event(1, "session.created", {"status": "queued_round_1"}),
        event(2, "job.queued", {"status": "queued_round_1"}),
        event(3, "job.started", {"status": "running_round_1"}),
    ]
    sequence = 3
    for item in r1_messages[:-1]:
        for event_type, payload in (
            ("turn.started", {"message_id": item["id"], "generation_id": item["generation_id"], "round_number": 1}),
            ("turn.delta", {"message_id": item["id"], "generation_id": item["generation_id"], "delta_index": 1, "delta": "Live ", "source": "live_provider"}),
            ("turn.citation", {"message_id": item["id"], "generation_id": item["generation_id"], "evidence_id": "E1", "citation_order": 1}),
            ("turn.completed", {"message": item, "round_number": 1}),
        ):
            sequence += 1
            r1_events.append(event(sequence, event_type, payload))
    # The live API carries round_number on the canonical Judge message; its
    # event envelope carries the semantic phase (interim/final).
    judge = r1_messages[-1]
    for event_type, payload in (
        ("judge.started", {"message_id": judge["id"], "generation_id": judge["generation_id"], "round_number": 1, "phase": "interim"}),
        ("judge.delta", {"message_id": judge["id"], "generation_id": judge["generation_id"], "round_number": 1, "phase": "interim", "delta_index": 1, "delta": "Live ", "source": "live_provider"}),
        ("turn.citation", {"message_id": judge["id"], "generation_id": judge["generation_id"], "evidence_id": "E1", "citation_order": 1}),
        ("judge.completed", {"message": judge, "phase": "interim"}),
    ):
        sequence += 1
        r1_events.append(event(sequence, event_type, payload))
    sequence += 1
    r1_events.append(event(sequence, "session.awaiting_user", {"status": "awaiting_user"}))
    round_one_terminal_sequence = sequence
    sequence += 1
    r2_events = [event(sequence, "job.queued", {"status": "queued_round_2", "generation_id": GENERATION_TWO})]
    sequence += 1
    r2_events.append(event(sequence, "job.started", {"status": "running_round_2", "generation_id": GENERATION_TWO}))
    for item in r2_messages[:-1]:
        for event_type, payload in (
            ("turn.started", {"message_id": item["id"], "generation_id": item["generation_id"], "round_number": 2}),
            ("turn.delta", {"message_id": item["id"], "generation_id": item["generation_id"], "delta_index": 1, "delta": "Live ", "source": "live_provider"}),
            ("turn.citation", {"message_id": item["id"], "generation_id": item["generation_id"], "evidence_id": "E1", "citation_order": 1}),
            ("turn.completed", {"message": item, "round_number": 2}),
        ):
            sequence += 1
            r2_events.append(event(sequence, event_type, payload))
    judge = r2_messages[-1]
    for event_type, payload in (
        ("judge.started", {"message_id": judge["id"], "generation_id": judge["generation_id"], "round_number": 2, "phase": "final"}),
        ("judge.delta", {"message_id": judge["id"], "generation_id": judge["generation_id"], "round_number": 2, "phase": "final", "delta_index": 1, "delta": "Live ", "source": "live_provider"}),
        ("turn.citation", {"message_id": judge["id"], "generation_id": judge["generation_id"], "evidence_id": "E1", "citation_order": 1}),
        ("judge.completed", {"message": judge, "phase": "final"}),
    ):
        sequence += 1
        r2_events.append(event(sequence, event_type, payload))
    sequence += 1
    r2_events.append(event(sequence, "session.completed", {"status": "completed"}))
    # The first connection in each phase intentionally ends after one event;
    # the verifier must reconnect from the last sequence.
    state["r1_events"] = r1_events
    state["r2_events"] = r2_events

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        state["requests"].append((request.method, path, dict(request.url.params)))
        state["headers"].append(request.headers.get("authorization"))
        if path == "/health":
            headers = {"x-commit-sha": SHA} if expose_sha_header else {}
            return httpx.Response(200, headers=headers, json={"status": "ok", "data_mode": "standard", "debate_workflow_v2": True})
        if path == "/debates" and request.method == "POST":
            return httpx.Response(202, json=initial_detail)
        if path.endswith("/events"):
            if state["fail_first_sse_connection"]:
                state["fail_first_sse_connection"] = False
                raise httpx.ConnectError("simulated SSE connect failure", request=request)
            cursor = int(request.url.params.get("after_sequence", "0"))
            phase_events = (
                state["r1_events"]
                if cursor < round_one_terminal_sequence
                else state["r2_events"]
            )
            if cursor == 0:
                selected = phase_events[:1]
            elif cursor == round_one_terminal_sequence:
                selected = phase_events[:1]
            elif cursor == round_one_terminal_sequence + 1:
                selected = phase_events[1:]
            else:
                selected = [item for item in phase_events if item["sequence"] > cursor]
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse(selected))
        if path.endswith("/interventions") and request.method == "POST":
            return httpx.Response(202, json=challenge_detail)
        if path.endswith("/provider-attempts"):
            round_two_admitted = any(
                item[1].endswith("/interventions") for item in state["requests"]
            )
            attempts_payload = (
                state["all_attempts"]
                if round_two_admitted
                else state["r1_attempts"]
            )
            return httpx.Response(
                200,
                json={
                    "attempts": attempts_payload,
                    "unknown_usage_attempts": sum(
                        item.get("usage_status") == "unknown" for item in attempts_payload
                    ),
                },
            )
        if path.endswith("/messages"):
            if any(item[1].endswith("/interventions") for item in state["requests"]):
                return httpx.Response(200, json=state["details"]["final"]["messages"])
            return httpx.Response(200, json=r1_records)
        if path.startswith("/debates/") and request.method == "GET":
            if any(item[1].endswith("/interventions") for item in state["requests"]):
                return httpx.Response(200, json=final_detail)
            return httpx.Response(200, json=r1_detail)
        raise AssertionError(f"unexpected request {request.method} {path}")

    return httpx.MockTransport(handle), state


def test_sse_parser_accepts_fragmented_data_and_comments() -> None:
    parser = SseFrameParser()
    payload = event(1, "heartbeat", {"latest_sequence": 0})
    raw = f": keepalive\r\nid: 1\r\nevent: heartbeat\r\ndata: {json.dumps(payload)}\r\n\r\n"
    output = []
    for chunk in (raw[:7], raw[7:19], raw[19:]):
        output.extend(parser.feed(chunk))
    assert output[0].sequence == 1
    assert output[0].event_type == "heartbeat"


def test_authenticated_api_keeps_stream_open_for_the_caller() -> None:
    payload = event(1, "heartbeat", {"latest_sequence": 0})

    class DelayedByteStream(httpx.SyncByteStream):
        def __iter__(self):
            yield sse([payload]).encode()

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            stream=DelayedByteStream(),
        )
    )
    client = httpx.Client(transport=transport)
    api = AuthenticatedApi(
        AcceptanceConfig(
            base_url="https://api.example.test",
            access_token="user-token",
            require_current_sha=False,
        ),
        client=client,
    )

    response = api.stream(SESSION_ID, 0)

    assert not response.is_closed
    assert list(response.iter_lines())
    response.close()
    assert response.is_closed


def test_current_sha_live_queue_verifier_uses_auth_and_resumes_sse_without_delete() -> None:
    transport, state = fixture_transport(include_r1_retry=False, max_attempts=1)
    client = httpx.Client(transport=transport)
    config = AcceptanceConfig(
        base_url="https://api.example.test",
        access_token="user-token",
        provider_request_budget=12,
        expected_sha=SHA,
    )
    report = verify_current_sha_live_queue(config, client=client)

    assert report["passed"]
    assert report["server_sha"] == SHA
    assert report["snapshot"]["price_count"] == 50
    assert report["observed_provider_requests"] == 12
    assert report["round_one_accounting"]["unknown_usage_attempts"] == 0
    assert report["cleanup"] == "skipped_no_exact_delete_endpoint"
    assert not any(method == "DELETE" for method, _, _ in state["requests"])
    assert any(path.endswith("/events") and params.get("after_sequence") == "1" for _, path, params in state["requests"])
    assert state["headers"]
    assert all(value == "Bearer user-token" for value in state["headers"])


def test_provider_budget_refuses_round_two_when_round_one_retry_uses_the_budget() -> None:
    transport, state = fixture_transport()
    # The fixture's Round 1 audit has eight attempts (one unknown failed
    # attempt plus seven completed slots), so a budget of twelve still leaves
    # only four requests and must refuse the challenge.
    config = AcceptanceConfig(
        base_url="https://api.example.test",
        access_token="token",
        require_current_sha=False,
        require_no_worker_retries=False,
    )
    client = httpx.Client(transport=transport)
    report = verify_current_sha_live_queue(config, client=client)
    assert not report["passed"]
    assert "insufficient room" in report["error"]
    assert not any(path.endswith("/interventions") for _, path, _ in state["requests"])

    # Config validation is the hard floor for the complete 12-request flow.
    with pytest.raises(ValueError, match="at least 12"):
        AcceptanceConfig(base_url="https://api.example.test", access_token="token", provider_request_budget=11)


def test_current_sha_mismatch_fails_before_admitting_a_debate() -> None:
    transport, state = fixture_transport(expose_sha_header=False)
    config = AcceptanceConfig(
        base_url="https://api.example.test",
        access_token="token",
        expected_sha=SHA,
    )

    report = verify_current_sha_live_queue(config, client=httpx.Client(transport=transport))

    assert not report["passed"]
    assert "preflight" in report["error"]
    assert not any(method == "POST" and path == "/debates" for method, path, _ in state["requests"])


def test_no_worker_retry_mode_checks_both_queued_jobs() -> None:
    transport, _ = fixture_transport(include_r1_retry=False, max_attempts=3)
    config = AcceptanceConfig(
        base_url="https://api.example.test",
        access_token="token",
        expected_sha=SHA,
        require_no_worker_retries=True,
    )

    report = verify_current_sha_live_queue(config, client=httpx.Client(transport=transport))

    assert not report["passed"]
    assert report["checks"]["worker_retry_policy"] is False
    assert report["checks"]["round_two_worker_retry_policy"] is False


def test_sse_connection_failure_reconnects_within_bound() -> None:
    transport, _ = fixture_transport(
        include_r1_retry=False,
        max_attempts=1,
        fail_first_sse_connection=True,
    )
    config = AcceptanceConfig(
        base_url="https://api.example.test",
        access_token="token",
        expected_sha=SHA,
        max_reconnects=2,
    )

    report = verify_current_sha_live_queue(config, client=httpx.Client(transport=transport))

    assert report["passed"]


def test_sse_connection_failure_respects_reconnect_bound() -> None:
    transport, _ = fixture_transport(
        include_r1_retry=False,
        max_attempts=1,
        fail_first_sse_connection=True,
    )
    config = AcceptanceConfig(
        base_url="https://api.example.test",
        access_token="token",
        expected_sha=SHA,
        max_reconnects=1,
    )

    report = verify_current_sha_live_queue(
        config,
        client=httpx.Client(transport=transport),
    )

    assert not report["passed"]
    assert "bounded reconnects" in report["error"]


def test_terminal_session_failure_stops_without_burning_reconnect_budget() -> None:
    transport, state = fixture_transport(include_r1_retry=False, max_attempts=1)
    state["r1_events"] = state["r1_events"][:3] + [
        event(
            4,
            "session.failed",
            {
                "status": "failed",
                "safe_error_code": "debate_execution_failed",
                "generation_id": GENERATION_ONE,
            },
        )
    ]
    config = AcceptanceConfig(
        base_url="https://api.example.test",
        access_token="token",
        expected_sha=SHA,
        max_reconnects=4,
    )

    report = verify_current_sha_live_queue(config, client=httpx.Client(transport=transport))

    assert not report["passed"]
    assert report["error"] == (
        "SSE 1 reached session.failed (debate_execution_failed) before "
        "session.awaiting_user"
    )
    assert sum(path.endswith("/events") for _, path, _ in state["requests"]) == 2
    assert not any(path.endswith("/interventions") for _, path, _ in state["requests"])


def test_deterministic_providers_cannot_pass_live_acceptance() -> None:
    transport, state = fixture_transport(include_r1_retry=False, max_attempts=1)
    for detail in state["details"].values():
        for item in detail["messages"]:
            message_payload = item["message"]
            if message_payload["role"] in {"bull", "bear"}:
                message_payload["metadata"]["provider"] = "deterministic-debate"
                message_payload["metadata"]["model_name"] = "deterministic-debate:v2-stream"
    for attempt in state["all_attempts"]:
        if attempt["role"] in {"bull", "bear"}:
            attempt["provider"] = "deterministic-debate"
            attempt["model"] = "deterministic-debate:v2-stream"

    report = verify_current_sha_live_queue(
        AcceptanceConfig(
            base_url="https://api.example.test",
            access_token="token",
            expected_sha=SHA,
        ),
        client=httpx.Client(transport=transport),
    )

    assert not report["passed"]
    assert report["checks"]["round_one_live_providers"] is False


def test_failed_only_attempt_cannot_cover_a_completed_message() -> None:
    transport, state = fixture_transport(include_r1_retry=False, max_attempts=1)
    state["r1_attempts"][0]["outcome"] = "failed"

    report = verify_current_sha_live_queue(
        AcceptanceConfig(
            base_url="https://api.example.test",
            access_token="token",
            expected_sha=SHA,
        ),
        client=httpx.Client(transport=transport),
    )

    assert not report["passed"]
    assert report["round_one_accounting"]["missing_completed_message_ids"]


def test_incomplete_market_snapshot_cannot_pass_current_data_acceptance() -> None:
    transport, state = fixture_transport(include_r1_retry=False, max_attempts=1)
    state["details"]["r1"]["session"]["analysis_context"]["prices"] = []

    report = verify_current_sha_live_queue(
        AcceptanceConfig(
            base_url="https://api.example.test",
            access_token="token",
            expected_sha=SHA,
        ),
        client=httpx.Client(transport=transport),
    )

    assert not report["passed"]
    assert report["checks"]["current_aapl_snapshot"] is False


def test_completed_events_without_live_deltas_cannot_pass() -> None:
    transport, state = fixture_transport(include_r1_retry=False, max_attempts=1)
    for item in state["r1_events"]:
        if item["type"] == "turn.delta":
            item["payload"]["source"] = "deterministic"

    report = verify_current_sha_live_queue(
        AcceptanceConfig(
            base_url="https://api.example.test",
            access_token="token",
            expected_sha=SHA,
        ),
        client=httpx.Client(transport=transport),
    )

    assert not report["passed"]
    assert report["checks"]["round_one_sse_interim_judge"] is False


def test_cli_allows_zero_reconnects() -> None:
    from scripts.verify_current_sha_live_queue import parse_args

    args = parse_args(
        [
            "--base-url",
            "https://api.example.test",
            "--token",
            "token",
            "--allow-missing-current-sha",
            "--max-reconnects",
            "0",
        ]
    )

    assert args.max_reconnects == 0
