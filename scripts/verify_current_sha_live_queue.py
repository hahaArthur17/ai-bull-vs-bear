#!/usr/bin/env python3
"""Verify one bounded, authenticated, current-build V2 Queue Debate.

This verifier is deliberately an HTTP client.  It does not import the API
application, reach a provider directly, refresh market data, or delete a
session.  A run creates one Debate for the supplied authenticated user and
therefore should use a dedicated acceptance account.  Cleanup is reported as
``skipped_no_exact_delete_endpoint`` unless an exact, user-supplied DELETE
endpoint is provided.

The minimum successful workflow consumes twelve provider requests: six
Bull/Bear turns and an Interim Judge in Round 1, followed by four turns and a
Final Judge in Round 2.  The verifier refuses the challenge when the observed
Round 1 ledger leaves less than five requests and fails the report if the final
ledger exceeds its configured budget.  The API Worker owns provider dispatch,
so an in-flight or server-side retry can cross the bound before this client
observes it; the report calls that limitation out explicitly.  A bounded
acceptance run requires ``max_attempts=1`` on each Job; this is enabled by
default and is checked when the Job responses expose that setting.

The default command does not run anything.  Network access only occurs when
``main`` is explicitly invoked with an API URL and bearer token.  Tests inject
an ``httpx.MockTransport`` and never contact an external service.  A passing
command requires ``--expected-sha`` (or ``EXPECTED_CURRENT_SHA``), a SHA from
the API health response or release header, and ``max_attempts=1`` on both
queued Jobs. ``--allow-missing-current-sha`` is an explicit diagnostic escape
hatch; the library verifier still reports a run without the no-retry policy as
not bounded.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
import re
from collections.abc import Callable, Iterable, Iterator, Sequence
from typing import Any
from uuid import uuid4

import httpx


DEFAULT_PROVIDER_REQUEST_BUDGET = 12
ROUND_ONE_PROVIDER_REQUESTS = 7
ROUND_TWO_PROVIDER_REQUESTS = 5
DEFAULT_MAX_RECONNECTS = 4
DEFAULT_HTTP_TIMEOUT_SECONDS = 30.0
DEFAULT_CHALLENGE = "Does this rebuttal underweight the filing risk?"
DEFAULT_EXPECTED_TURN_PROVIDER = "groq-live-debate"
DEFAULT_EXPECTED_JUDGE_PROVIDER = "groq-live-judge"
EXPECTED_MACRO_SERIES = frozenset({
    "effective_fed_funds_rate",
    "sp500",
    "treasury_10y_yield",
    "treasury_2y_yield",
    "treasury_30y_yield",
    "vix",
    "wti_spot",
})
SHA_KEYS = ("commit_sha", "git_sha", "release_sha", "build_sha", "source_sha")
SHA_HEADER_KEYS = ("x-commit-sha", "x-git-sha", "x-release-sha", "x-build-sha")
_HEX_SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")


class AcceptanceError(RuntimeError):
    """A safe, actionable acceptance failure without response-body leakage."""


class SseConnectionError(AcceptanceError):
    """An SSE connection failed before a response could be consumed."""


class HttpApiError(AcceptanceError):
    def __init__(self, method: str, path: str, status_code: int) -> None:
        self.method = method
        self.path = path
        self.status_code = status_code
        super().__init__(f"HTTP {method} {path} returned {status_code}")


@dataclass(frozen=True)
class AcceptanceConfig:
    base_url: str
    access_token: str
    provider_request_budget: int = DEFAULT_PROVIDER_REQUEST_BUDGET
    expected_sha: str | None = None
    expected_turn_provider: str = DEFAULT_EXPECTED_TURN_PROVIDER
    expected_judge_provider: str = DEFAULT_EXPECTED_JUDGE_PROVIDER
    require_current_sha: bool = True
    allow_missing_provider_audit: bool = False
    require_no_worker_retries: bool = True
    max_reconnects: int = DEFAULT_MAX_RECONNECTS
    timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS
    cleanup_endpoint_template: str | None = None

    def __post_init__(self) -> None:
        if not self.base_url.strip():
            raise ValueError("An API base URL is required")
        if not self.access_token.strip():
            raise ValueError("An authenticated API token is required")
        if self.provider_request_budget < DEFAULT_PROVIDER_REQUEST_BUDGET:
            raise ValueError(
                "The full two-round Debate requires a provider budget of at least 12"
            )
        if (
            not isinstance(self.max_reconnects, int)
            or isinstance(self.max_reconnects, bool)
            or self.max_reconnects < 0
        ):
            raise ValueError("max_reconnects cannot be negative")
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if self.expected_sha is not None and not _HEX_SHA.fullmatch(self.expected_sha):
            raise ValueError("expected_sha must be a 7-64 character hexadecimal SHA")
        if not self.expected_turn_provider.strip():
            raise ValueError("expected_turn_provider cannot be blank")
        if not self.expected_judge_provider.strip():
            raise ValueError("expected_judge_provider cannot be blank")


@dataclass(frozen=True)
class SseEvent:
    sequence: int
    event_type: str
    payload: dict[str, Any]
    event_id: str | None = None


class SseFrameParser:
    """Small standards-compatible SSE parser that tolerates chunk boundaries."""

    def __init__(self) -> None:
        self._buffer = ""
        self._event = "message"
        self._event_id: str | None = None
        self._data: list[str] = []

    def feed(self, chunk: str | bytes) -> Iterator[SseEvent]:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        self._buffer += chunk.replace("\r\n", "\n").replace("\r", "\n")
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            event = self._consume_line(line)
            if event is not None:
                yield event

    def close(self) -> Iterator[SseEvent]:
        if self._buffer:
            event = self._consume_line(self._buffer)
            self._buffer = ""
            if event is not None:
                yield event
        event = self._dispatch()
        if event is not None:
            yield event

    def _consume_line(self, line: str) -> SseEvent | None:
        if line == "":
            return self._dispatch()
        if line.startswith(":"):
            return None
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            self._event = value
        elif field == "id":
            self._event_id = value
        elif field == "data":
            self._data.append(value)
        return None

    def _dispatch(self) -> SseEvent | None:
        if not self._data:
            self._event = "message"
            self._event_id = None
            return None
        raw = "\n".join(self._data)
        event_name = self._event
        event_id = self._event_id
        self._event = "message"
        self._event_id = None
        self._data = []
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            raise AcceptanceError("SSE frame did not contain valid JSON") from exc
        if not isinstance(payload, dict):
            raise AcceptanceError("SSE frame payload was not an object")
        sequence = payload.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
            raise AcceptanceError("SSE frame has an invalid event sequence")
        payload_type = payload.get("type")
        if payload_type != event_name:
            raise AcceptanceError("SSE event name does not match its envelope")
        return SseEvent(
            sequence=sequence,
            event_type=event_name,
            payload=payload,
            event_id=event_id,
        )


@dataclass
class ProviderBudget:
    limit: int
    observed: int = 0

    def observe(self, attempts: Sequence[dict[str, Any]]) -> None:
        self.observed = len(attempts)
        if self.observed > self.limit:
            raise AcceptanceError(
                f"Provider request budget exceeded ({self.observed}>{self.limit})"
            )

    def require_room(self, required: int) -> None:
        if required < 0 or self.observed + required > self.limit:
            raise AcceptanceError(
                "Provider request budget leaves insufficient room for Round 2"
            )


class AuthenticatedApi:
    """Authenticated API transport; no request is made during construction."""

    def __init__(
        self,
        config: AcceptanceConfig,
        *,
        client: httpx.Client | None = None,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.config = config
        self.base_url = config.base_url.strip().rstrip("/")
        self._client = client or (
            client_factory() if client_factory is not None else httpx.Client(
                timeout=config.timeout_seconds
            )
        )
        self._owns_client = client is None

    @property
    def client(self) -> httpx.Client:
        return self._client

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: object | None = None,
        accept: str = "application/json",
    ) -> httpx.Response:
        if not path.startswith("/"):
            raise ValueError("API paths must start with '/'")
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {self.config.access_token}",
        }
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = self._client.request(
                method,
                f"{self.base_url}{path}",
                params=params,
                json=json_body,
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise AcceptanceError(f"HTTP {method} {path} failed before a response") from exc
        return response

    def json_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: object | None = None,
        statuses: set[int] = {200},
    ) -> tuple[httpx.Response, dict[str, Any] | list[Any] | None]:
        response = self.request(method, path, params=params, json_body=json_body)
        if response.status_code not in statuses:
            raise HttpApiError(method, path, response.status_code)
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise AcceptanceError(f"HTTP {method} {path} returned invalid JSON") from exc
        if body is not None and not isinstance(body, (dict, list)):
            raise AcceptanceError(f"HTTP {method} {path} returned an invalid JSON shape")
        return response, body

    def stream(self, session_id: str, after_sequence: int) -> httpx.Response:
        """Open one resumable SSE request; caller owns the response context."""

        if after_sequence < 0:
            raise ValueError("SSE cursor cannot be negative")
        try:
            request = self._client.build_request(
                "GET",
                f"{self.base_url}/debates/{session_id}/events",
                params={"after_sequence": str(after_sequence)},
                headers={
                    "Accept": "text/event-stream",
                    "Authorization": f"Bearer {self.config.access_token}",
                },
            )
            return self._client.send(request, stream=True)
        except httpx.RequestError as exc:
            raise SseConnectionError("SSE connection failed before a response") from exc


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AcceptanceError(f"{label} was not an object")
    return value


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AcceptanceError(f"{label} was missing")
    return value


def _session_id(detail: dict[str, Any]) -> str:
    session = _object(detail.get("session"), "Debate session")
    return _required_string(session.get("id"), "Debate session id")


def _messages(detail: dict[str, Any]) -> list[dict[str, Any]]:
    raw = detail.get("messages")
    if not isinstance(raw, list):
        raise AcceptanceError("Debate detail did not contain a message list")
    return [_object(item, "Debate message record") for item in raw]


def _message(record: dict[str, Any]) -> dict[str, Any]:
    return _object(record.get("message"), "Debate message")


def _role_counts(messages: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for message in messages:
        role = message.get("role")
        if isinstance(role, str):
            counts[role] = counts.get(role, 0) + 1
    return counts


def _metadata(message: dict[str, Any]) -> dict[str, Any]:
    metadata = message.get("metadata", {})
    return metadata if isinstance(metadata, dict) else {}


def _extract_sha(payload: dict[str, Any], headers: httpx.Headers) -> str | None:
    for key in SHA_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    build = payload.get("build")
    if isinstance(build, dict):
        for key in SHA_KEYS:
            value = build.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in SHA_HEADER_KEYS:
        value = headers.get(key)
        if value and value.strip():
            return value.strip()
    return None


def _sha_matches(expected: str, actual: str) -> bool:
    expected = expected.strip().lower()
    actual = actual.strip().lower()
    return actual == expected or (len(expected) < 40 and actual.startswith(expected))


def _phase_for_message(message: dict[str, Any]) -> int | None:
    value = message.get("round_number")
    return value if isinstance(value, int) and not isinstance(value, bool) and value in {1, 2} else None


def _canonical_ids(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        message = _message(record)
        identifier = message.get("id")
        if not isinstance(identifier, str) or not identifier:
            raise AcceptanceError("Canonical message is missing its id")
        if identifier in output:
            raise AcceptanceError("Canonical transcript contains duplicate message ids")
        output[identifier] = message
    return output


def _check_citations(
    records: Iterable[dict[str, Any]],
    *,
    allowed_evidence_ids: set[str],
) -> tuple[bool, int]:
    total = 0
    passed = True
    has_citable_message = False
    for record in records:
        message = _message(record)
        if message.get("role") not in {"bull", "bear", "judge"}:
            continue
        has_citable_message = True
        citations = record.get("citations")
        if not isinstance(citations, list) or not citations:
            passed = False
            continue
        orders: list[int] = []
        evidence_ids: set[str] = set()
        for citation in citations:
            if not isinstance(citation, dict):
                passed = False
                continue
            if citation.get("message_id") != message.get("id"):
                passed = False
            evidence_id = citation.get("evidence_id")
            if not isinstance(evidence_id, str) or not evidence_id:
                passed = False
            elif allowed_evidence_ids and evidence_id not in allowed_evidence_ids:
                passed = False
            elif evidence_id in evidence_ids:
                passed = False
            else:
                evidence_ids.add(evidence_id)
            order = citation.get("citation_order")
            if not isinstance(order, int) or isinstance(order, bool) or order < 1:
                passed = False
            else:
                orders.append(order)
            total += 1
        if orders != list(range(1, len(orders) + 1)):
            passed = False
    if has_citable_message and not allowed_evidence_ids:
        passed = False
    return passed, total


def _check_provider_metadata(
    records: Iterable[dict[str, Any]],
) -> tuple[bool, dict[str, list[str]]]:
    # Turn messages currently carry provider/version and stream mode.  Their
    # model is authoritative in the provider-attempt ledger; Judge messages
    # also copy model_name into metadata when usage is reported.
    passed = True
    by_role: dict[str, set[tuple[str, str]]] = {}
    for record in records:
        message = _message(record)
        role = message.get("role")
        if role not in {"bull", "bear", "judge"} or message.get("is_complete") is not True:
            continue
        metadata = _metadata(message)
        provider = metadata.get("provider")
        model = metadata.get("model_name")
        provider_version = metadata.get("provider_version")
        stream_mode = metadata.get("stream_mode")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (provider, provider_version)
        ):
            passed = False
            continue
        if stream_mode != "async_provider":
            passed = False
        by_role.setdefault(str(role), set()).add(
            (str(provider), str(model) if isinstance(model, str) and model.strip() else "unknown-model")
        )
        usage = metadata.get("usage")
        if usage is not None:
            if not isinstance(usage, dict):
                passed = False
                continue
            token_values = [usage.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")]
            if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in token_values):
                passed = False
            elif token_values[2] != token_values[0] + token_values[1]:
                passed = False
    normalized = {
        role: sorted(f"{provider}:{model}" for provider, model in values)
        for role, values in by_role.items()
    }
    return passed and set(normalized) >= {"bull", "bear", "judge"}, normalized


def _check_expected_providers(
    provider_models: dict[str, list[str]],
    *,
    expected_turn_provider: str,
    expected_judge_provider: str,
) -> bool:
    expected_by_role = {
        "bull": expected_turn_provider,
        "bear": expected_turn_provider,
        "judge": expected_judge_provider,
    }
    for role, expected_provider in expected_by_role.items():
        observed = provider_models.get(role, [])
        if not observed or any(
            not provider_model.startswith(f"{expected_provider}:")
            for provider_model in observed
        ):
            return False
    return True


def _snapshot_summary(context: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    prices = context.get("prices")
    evidence = context.get("evidence")
    macro = context.get("macro_context")
    financial = context.get("financial_facts")
    quote = context.get("market_quote")
    prices = prices if isinstance(prices, list) else []
    evidence = evidence if isinstance(evidence, list) else []
    macro = macro if isinstance(macro, list) else []
    financial = financial if isinstance(financial, list) else []
    quote = quote if isinstance(quote, dict) else {}

    price_dates = [
        item.get("date")
        for item in prices
        if isinstance(item, dict) and isinstance(item.get("date"), str)
    ]
    price_sources = sorted({
        str(item.get("source"))
        for item in prices
        if isinstance(item, dict) and isinstance(item.get("source"), str)
    })
    evidence_items = [item for item in evidence if isinstance(item, dict)]
    macro_items = [item for item in macro if isinstance(item, dict)]
    financial_items = [item for item in financial if isinstance(item, dict)]
    evidence_types = sorted({
        str(item.get("source_type")) for item in evidence_items
        if isinstance(item.get("source_type"), str)
    })
    macro_codes = sorted({
        str(item.get("code")) for item in macro_items
        if isinstance(item.get("code"), str)
    })
    quote_freshness = quote.get("freshness")
    quote_freshness = quote_freshness if isinstance(quote_freshness, dict) else {}
    snapshot_valid = (
        context.get("ticker") == "AAPL"
        and isinstance(context.get("as_of"), str)
        and bool(context.get("as_of"))
        and isinstance(context.get("captured_at"), str)
        and bool(context.get("captured_at"))
        and len(prices) >= 50
        and len(price_dates) == len(prices)
        and price_dates == sorted(set(price_dates))
        and context.get("latest_completed_close_date") == price_dates[-1]
        and all(
            isinstance(item, dict)
            and item.get("source") == "daily_market_cache"
            and item.get("is_stale") is False
            for item in prices
        )
        and quote.get("ticker") == "AAPL"
        and quote.get("source") == "finnhub_quote"
        and isinstance(quote.get("as_of"), str)
        and isinstance(quote.get("retrieved_at"), str)
        and quote_freshness.get("status") == "current"
        and {"news", "filing"} <= set(evidence_types)
        and all(
            isinstance(item.get("published_at"), str)
            and isinstance(item.get("freshness"), dict)
            and item["freshness"].get("status") == "current"
            for item in evidence_items
        )
        and set(macro_codes) == EXPECTED_MACRO_SERIES
        and len(macro_items) == len(EXPECTED_MACRO_SERIES)
        and all(
            isinstance(item.get("observation_date"), str)
            and isinstance(item.get("retrieved_at"), str)
            for item in macro_items
        )
        and bool(financial_items)
        and all(
            item.get("form") in {"10-K", "10-Q"}
            and isinstance(item.get("filed_at"), str)
            and isinstance(item.get("period_end"), str)
            for item in financial_items
        )
    )
    summary = {
        "ticker": context.get("ticker"),
        "as_of": context.get("as_of"),
        "captured_at": context.get("captured_at"),
        "latest_completed_close_date": context.get("latest_completed_close_date"),
        "price_count": len(prices),
        "price_sources": price_sources,
        "evidence_count": len(evidence_items),
        "evidence_source_types": evidence_types,
        "macro_count": len(macro_items),
        "macro_codes": macro_codes,
        "financial_fact_count": len(financial_items),
        "quote": {
            "source": quote.get("source"),
            "as_of": quote.get("as_of"),
            "retrieved_at": quote.get("retrieved_at"),
            "freshness": quote_freshness.get("status"),
            "market_session": quote.get("market_session"),
        },
    }
    return snapshot_valid, summary


def _check_attempts(
    attempts_payload: dict[str, Any],
    *,
    phase: int,
    expected_attempts: int,
    messages_by_id: dict[str, dict[str, Any]],
    budget: ProviderBudget,
    job: dict[str, Any] | None,
    require_single_attempt_per_message: bool = False,
) -> dict[str, Any]:
    raw_attempts = attempts_payload.get("attempts")
    if not isinstance(raw_attempts, list):
        raise AcceptanceError("Provider audit did not contain an attempts list")
    attempts = [_object(item, "Provider attempt") for item in raw_attempts]
    budget.observe(attempts)
    phase_attempts: list[dict[str, Any]] = []
    attempt_ids: set[str] = set()
    phase_message_ids: set[str] = {
        identifier
        for identifier, message in messages_by_id.items()
        if _phase_for_message(message) == phase
        and message.get("role") in {"bull", "bear", "judge"}
    }
    phase_attempt_message_ids: set[str] = set()
    completed_message_ids: set[str] = set()
    duplicate_message_ids: set[str] = set()
    attempts_valid = True
    for attempt in attempts:
        attempt_id = attempt.get("id")
        if not isinstance(attempt_id, str) or not attempt_id.strip() or attempt_id in attempt_ids:
            attempts_valid = False
        elif attempt_id:
            attempt_ids.add(attempt_id)
        message_id = attempt.get("message_id")
        if not isinstance(message_id, str) or not message_id:
            attempts_valid = False
            continue
        message = messages_by_id.get(message_id)
        if message is None:
            # Every billed provider request must point at a canonical message
            # in this Debate. Counting an orphan row toward the budget while
            # ignoring it for role checks could otherwise produce a false pass.
            attempts_valid = False
            continue
        if (
            attempt.get("session_id") != message.get("session_id")
            or attempt.get("generation_id") != message.get("generation_id")
            or attempt.get("role") != message.get("role")
        ):
            attempts_valid = False
        if _phase_for_message(message) == phase:
            phase_attempts.append(attempt)
            if message_id in phase_attempt_message_ids:
                duplicate_message_ids.add(message_id)
            phase_attempt_message_ids.add(message_id)
            if attempt.get("outcome") == "completed":
                completed_message_ids.add(message_id)
    phase_roles = _role_counts(
        {"role": attempt.get("role")} for attempt in phase_attempts
    )
    expected_roles = {"bull": 3, "bear": 3, "judge": 1} if phase == 1 else {"bull": 2, "bear": 2, "judge": 1}
    usage_unknown = 0
    reported_prompt = reported_completion = reported_total = 0
    metadata_passed = True
    for attempt in phase_attempts:
        if not isinstance(attempt.get("admitted_at"), str) or not attempt.get("admitted_at", "").strip():
            metadata_passed = False
        for timestamp_key in ("dispatched_at", "finished_at"):
            timestamp = attempt.get(timestamp_key)
            if timestamp is not None and (
                not isinstance(timestamp, str) or not timestamp.strip()
            ):
                metadata_passed = False
        provider = attempt.get("provider")
        model = attempt.get("model")
        if not all(isinstance(value, str) and value.strip() for value in (provider, model)):
            metadata_passed = False
        canonical = messages_by_id.get(str(attempt.get("message_id")))
        canonical_metadata = _metadata(canonical) if canonical is not None else {}
        if (
            isinstance(canonical_metadata.get("provider"), str)
            and canonical_metadata.get("provider") != provider
        ) or (
            isinstance(canonical_metadata.get("model_name"), str)
            and canonical_metadata.get("model_name") != model
        ):
            metadata_passed = False
        if attempt.get("outcome") not in {"completed", "failed"}:
            metadata_passed = False
        if not attempt.get("dispatched_at") or not attempt.get("finished_at"):
            metadata_passed = False
        usage_status = attempt.get("usage_status")
        values = [attempt.get(key) for key in ("prompt_tokens", "completion_tokens", "total_tokens")]
        if usage_status == "unknown":
            usage_unknown += 1
            if any(value is not None for value in values):
                metadata_passed = False
        elif usage_status == "reported":
            if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in values):
                metadata_passed = False
            elif values[2] != values[0] + values[1]:
                metadata_passed = False
            else:
                reported_prompt += values[0]
                reported_completion += values[1]
                reported_total += values[2]
        else:
            metadata_passed = False
        if attempt.get("outcome") == "completed" and (
            usage_status != "reported"
            or not isinstance(attempt.get("total_tokens"), int)
            or isinstance(attempt.get("total_tokens"), bool)
            or attempt.get("total_tokens", 0) <= 0
        ):
            metadata_passed = False
    summary_checks = True
    all_reported_total = sum(
        attempt.get("total_tokens", 0)
        for attempt in attempts
        if attempt.get("usage_status") == "reported"
        and isinstance(attempt.get("total_tokens"), int)
    )
    all_unknown_usage = sum(
        attempt.get("usage_status") == "unknown" for attempt in attempts
    )
    summary_values = {
        "admitted_count": len(attempts),
        "dispatch_attempts": sum(bool(attempt.get("dispatched_at")) for attempt in attempts),
        "reported_tokens": all_reported_total,
        "unknown_usage_attempts": all_unknown_usage,
    }
    for key, expected in summary_values.items():
        if key in attempts_payload and attempts_payload.get(key) != expected:
            summary_checks = False
    job_accounting = True
    if job is not None:
        provider_request_count = job.get("provider_request_count")
        prompt_tokens = job.get("prompt_tokens")
        completion_tokens = job.get("completion_tokens")
        total_tokens = job.get("total_tokens")
        job_accounting = (
            isinstance(provider_request_count, int)
            and provider_request_count == len(phase_attempts)
            and isinstance(prompt_tokens, int)
            and prompt_tokens == reported_prompt
            and isinstance(completion_tokens, int)
            and completion_tokens == reported_completion
            and isinstance(total_tokens, int)
            and total_tokens == reported_total
        )
    missing_message_ids = sorted(phase_message_ids - phase_attempt_message_ids)
    missing_completed_message_ids = sorted(phase_message_ids - completed_message_ids)
    required_slots_passed = not missing_message_ids and (
        not require_single_attempt_per_message
        or (not duplicate_message_ids and len(phase_attempts) == expected_attempts)
    )
    return {
        "passed": (
            attempts_valid
            and required_slots_passed
            and not missing_completed_message_ids
            and len(phase_attempts) >= expected_attempts
            # A temporary provider failure may leave an additional failed
            # attempt for the same canonical message.  The ledger therefore
            # may contain more attempts than plan slots, while every planned
            # role still needs at least one attempt.
            and set(phase_roles) <= set(expected_roles)
            and all(phase_roles.get(role, 0) >= count for role, count in expected_roles.items())
            and metadata_passed
            and summary_checks
            and job_accounting
        ),
        "attempt_count": len(phase_attempts),
        "expected_attempts": expected_attempts,
        "roles": phase_roles,
        "reported_prompt_tokens": reported_prompt,
        "reported_completion_tokens": reported_completion,
        "reported_total_tokens": reported_total,
        "unknown_usage_attempts": usage_unknown,
        "attempt_rows_valid": attempts_valid,
        "attempt_metadata_valid": metadata_passed,
        "job_accounting": job_accounting,
        "summary_accounting": summary_checks,
        "missing_message_ids": missing_message_ids,
        "missing_completed_message_ids": missing_completed_message_ids,
        "duplicate_message_ids": sorted(duplicate_message_ids),
    }


def _summarize_failure_attempts(
    attempts_payload: dict[str, Any],
    *,
    budget: ProviderBudget,
) -> dict[str, Any]:
    """Retain safe provider accounting when a workflow fails before a phase gate."""

    raw_attempts = attempts_payload.get("attempts")
    if not isinstance(raw_attempts, list):
        raise AcceptanceError("Provider audit did not contain an attempts list")
    attempts = [_object(item, "Provider attempt") for item in raw_attempts]
    budget.observe(attempts)
    reported_prompt = reported_completion = reported_total = 0
    unknown_usage = 0
    usage_valid = True
    for attempt in attempts:
        usage_status = attempt.get("usage_status")
        values = tuple(
            attempt.get(key)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        )
        if usage_status == "unknown":
            unknown_usage += 1
            usage_valid = usage_valid and all(value is None for value in values)
        elif usage_status == "reported":
            valid_values = all(
                isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
                for value in values
            )
            if not valid_values or values[2] != values[0] + values[1]:
                usage_valid = False
            else:
                reported_prompt += values[0]
                reported_completion += values[1]
                reported_total += values[2]
        else:
            usage_valid = False
    dispatched = sum(bool(attempt.get("dispatched_at")) for attempt in attempts)
    summary_values = {
        "admitted_count": len(attempts),
        "dispatch_attempts": dispatched,
        "reported_tokens": reported_total,
        "unknown_usage_attempts": unknown_usage,
    }
    summary_matches = all(
        key not in attempts_payload or attempts_payload.get(key) == expected
        for key, expected in summary_values.items()
    )
    return {
        **summary_values,
        "completed_attempts": sum(
            attempt.get("outcome") == "completed" for attempt in attempts
        ),
        "failed_attempts": sum(
            attempt.get("outcome") == "failed" for attempt in attempts
        ),
        "unsettled_attempts": sum(
            attempt.get("outcome") not in {"completed", "failed"}
            for attempt in attempts
        ),
        "reported_prompt_tokens": reported_prompt,
        "reported_completion_tokens": reported_completion,
        "usage_valid": usage_valid,
        "summary_accounting": summary_matches,
    }


def _event_message(event: SseEvent) -> dict[str, Any] | None:
    nested = event.payload.get("payload")
    if not isinstance(nested, dict):
        return None
    message = nested.get("message")
    return message if isinstance(message, dict) else None


def _event_payload(event: SseEvent) -> dict[str, Any]:
    nested = event.payload.get("payload")
    return nested if isinstance(nested, dict) else {}


def _event_message_id(event: SseEvent) -> str | None:
    nested = _event_payload(event)
    message = nested.get("message")
    value = message.get("id") if isinstance(message, dict) else nested.get("message_id")
    return value if isinstance(value, str) and value else None


def _check_phase_events(events: Sequence[SseEvent], *, phase: int) -> dict[str, Any]:
    job_started = [event for event in events if event.event_type == "job.started"]
    turn_started = [event for event in events if event.event_type == "turn.started"]
    turn_deltas = [event for event in events if event.event_type == "turn.delta"]
    turn_events = [event for event in events if event.event_type == "turn.completed"]
    judge_started = [event for event in events if event.event_type == "judge.started"]
    judge_deltas = [event for event in events if event.event_type == "judge.delta"]
    judge_events = [event for event in events if event.event_type == "judge.completed"]
    citations = [event for event in events if event.event_type == "turn.citation"]
    expected_turns = 6 if phase == 1 else 4
    turn_messages = [_event_message(event) for event in turn_events]
    turn_messages = [message for message in turn_messages if message is not None]
    judge_messages = [_event_message(event) for event in judge_events]
    judge_messages = [message for message in judge_messages if message is not None]
    roles = _role_counts(turn_messages)
    completed_messages = turn_messages + judge_messages
    completed_by_id = {
        str(message.get("id")): message
        for message in completed_messages
        if isinstance(message.get("id"), str) and message.get("id")
    }
    completed_ids = set(completed_by_id)
    started_ids = {
        identifier
        for identifier in map(_event_message_id, turn_started + judge_started)
        if identifier is not None
    }
    delta_ids = {
        identifier
        for identifier in map(_event_message_id, turn_deltas + judge_deltas)
        if identifier is not None
    }
    citation_ids = {
        identifier
        for identifier in map(_event_message_id, citations)
        if identifier is not None
    }
    stream_events_valid = True
    delta_indices: dict[str, list[int]] = {}
    for stream_event in turn_started + turn_deltas + judge_started + judge_deltas + citations:
        identifier = _event_message_id(stream_event)
        message = completed_by_id.get(identifier or "")
        nested = _event_payload(stream_event)
        if (
            message is None
            or nested.get("generation_id") != message.get("generation_id")
        ):
            stream_events_valid = False
        if stream_event.event_type in {"turn.delta", "judge.delta"}:
            delta = nested.get("delta")
            delta_index = nested.get("delta_index")
            if (
                not isinstance(delta, str)
                or not delta
                or nested.get("source") != "live_provider"
                or not isinstance(delta_index, int)
                or isinstance(delta_index, bool)
                or delta_index < 1
                or identifier is None
            ):
                stream_events_valid = False
            elif identifier is not None:
                delta_indices.setdefault(identifier, []).append(delta_index)
    if any(
        indices != list(range(1, len(indices) + 1))
        for indices in delta_indices.values()
    ):
        stream_events_valid = False
    judge_rounds: list[object] = []
    judge_phases: list[object] = []
    for event in judge_events:
        nested = event.payload.get("payload")
        if isinstance(nested, dict):
            nested_message = nested.get("message")
            judge_rounds.append(
                nested.get("round_number")
                if "round_number" in nested
                else nested_message.get("round_number")
                if isinstance(nested_message, dict)
                else None
            )
            judge_phases.append(nested.get("phase"))
        else:
            judge_rounds.append(None)
            judge_phases.append(None)
    return {
        "passed": (
            len(turn_events) == expected_turns
            and len(judge_events) == 1
            and len(job_started) == 1
            and len(turn_started) == expected_turns
            and len(judge_started) == 1
            and roles == {"bull": expected_turns // 2, "bear": expected_turns // 2}
            and len(turn_messages) == len(turn_events)
            and all(
                isinstance(message.get("round_number"), int)
                and not isinstance(message.get("round_number"), bool)
                and message.get("round_number") == phase
                for message in turn_messages
            )
            and len(judge_messages) == len(judge_events)
            and all(
                message.get("role") == "judge"
                and isinstance(message.get("round_number"), int)
                and not isinstance(message.get("round_number"), bool)
                and message.get("round_number") == phase
                for message in judge_messages
            )
            and judge_rounds == [phase]
            and judge_phases == (["interim"] if phase == 1 else ["final"])
            and len(completed_by_id) == expected_turns + 1
            and started_ids == completed_ids
            and delta_ids == completed_ids
            and citation_ids == completed_ids
            and stream_events_valid
        ),
        "job_started": len(job_started),
        "turn_started": len(turn_started),
        "turn_deltas": len(turn_deltas),
        "turn_completed": len(turn_events),
        "judge_started": len(judge_started),
        "judge_deltas": len(judge_deltas),
        "judge_completed": len(judge_events),
        "citation_events": len(citations),
        "last_event": events[-1].event_type if events else None,
    }


class CurrentShaLiveQueueVerifier:
    def __init__(self, api: AuthenticatedApi) -> None:
        self.api = api
        self.config = api.config
        self.budget = ProviderBudget(self.config.provider_request_budget)
        self.session_id: str | None = None
        self.cleanup_status = "skipped_no_exact_delete_endpoint"
        self._provider_audit_available = True

    def _reload(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if self.session_id is None:
            raise AcceptanceError("Cannot reload before Debate admission")
        _, detail_body = self.api.json_request("GET", f"/debates/{self.session_id}")
        detail = _object(detail_body, "Debate detail")
        _, messages_body = self.api.json_request("GET", f"/debates/{self.session_id}/messages")
        if not isinstance(messages_body, list):
            raise AcceptanceError("Debate messages endpoint did not return a list")
        messages = [_object(item, "Debate message record") for item in messages_body]
        detail_ids = [str(_message(record).get("id")) for record in _messages(detail)]
        message_ids = [str(_message(record).get("id")) for record in messages]
        if detail_ids != message_ids:
            raise AcceptanceError("Detail and canonical message reloads disagree")
        return detail, messages

    def _provider_attempts(self, messages_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if self.session_id is None:
            raise AcceptanceError("Cannot read provider audit before Debate admission")
        response = self.api.request("GET", f"/debates/{self.session_id}/provider-attempts")
        if response.status_code in {404, 405}:
            if not self.config.allow_missing_provider_audit:
                raise AcceptanceError(
                    "Provider-attempt audit is unavailable; pass --allow-missing-provider-audit "
                    "only when the deployed API intentionally lacks this route"
                )
            self._provider_audit_available = False
            return {"attempts": []}
        if response.status_code != 200:
            raise HttpApiError("GET", f"/debates/{self.session_id}/provider-attempts", response.status_code)
        try:
            payload = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raise AcceptanceError("Provider audit returned invalid JSON") from exc
        return _object(payload, "Provider audit")

    def _stream_phase(
        self,
        *,
        after_sequence: int,
        terminal_type: str,
        phase: int,
    ) -> list[SseEvent]:
        if self.session_id is None:
            raise AcceptanceError("Cannot stream before Debate admission")
        cursor = after_sequence
        events: list[SseEvent] = []
        reconnects = 0
        while reconnects <= self.config.max_reconnects:
            response: httpx.Response | None = None
            try:
                response = self.api.stream(self.session_id, cursor)
                if response.status_code == 409:
                    latest_header = response.headers.get("x-debate-latest-sequence")
                    try:
                        latest = int(latest_header or "-1")
                    except ValueError as exc:
                        raise AcceptanceError("Expired SSE cursor had no valid latest sequence") from exc
                    if latest < cursor:
                        raise AcceptanceError("Expired SSE cursor moved backwards")
                    # Reloading here proves that cursor recovery uses canonical
                    # state before attaching to newer transient events.
                    detail, _ = self._reload()
                    status = _object(detail.get("session"), "Debate session").get("status")
                    if status in {"awaiting_user", "completed", "failed", "cancelled"} and latest == cursor:
                        break
                    cursor = latest
                    reconnects += 1
                    continue
                if response.status_code != 200:
                    raise HttpApiError("GET", f"/debates/{self.session_id}/events", response.status_code)
                parser = SseFrameParser()
                saw_terminal = False
                for line in response.iter_lines():
                    for event in parser.feed(line + "\n"):
                        if event.payload.get("session_id") != self.session_id:
                            raise AcceptanceError("SSE event belonged to another Debate session")
                        if event.event_type == "heartbeat":
                            continue
                        if event.event_id is not None and event.event_id != str(event.sequence):
                            raise AcceptanceError("SSE id did not match its event sequence")
                        if event.sequence <= cursor or event.sequence != cursor + 1:
                            raise AcceptanceError("SSE event sequence was not contiguous from the cursor")
                        cursor = event.sequence
                        events.append(event)
                        if event.event_type in {"session.failed", "session.cancelled"}:
                            nested = _event_payload(event)
                            safe_error_code = nested.get("safe_error_code")
                            suffix = (
                                f" ({safe_error_code})"
                                if isinstance(safe_error_code, str) and safe_error_code
                                else ""
                            )
                            raise AcceptanceError(
                                f"SSE {phase} reached {event.event_type}{suffix} before "
                                f"{terminal_type}"
                            )
                        if event.event_type == terminal_type:
                            saw_terminal = True
                            break
                    if saw_terminal:
                        break
                if not saw_terminal:
                    for event in parser.close():
                        if event.event_type == "heartbeat":
                            continue
                        if event.event_id is not None and event.event_id != str(event.sequence):
                            raise AcceptanceError("SSE id did not match its event sequence")
                        if event.payload.get("session_id") != self.session_id:
                            raise AcceptanceError("SSE event belonged to another Debate session")
                        if event.sequence <= cursor or event.sequence != cursor + 1:
                            raise AcceptanceError("SSE event sequence was not contiguous from the cursor")
                        cursor = event.sequence
                        events.append(event)
                        if event.event_type in {"session.failed", "session.cancelled"}:
                            nested = _event_payload(event)
                            safe_error_code = nested.get("safe_error_code")
                            suffix = (
                                f" ({safe_error_code})"
                                if isinstance(safe_error_code, str) and safe_error_code
                                else ""
                            )
                            raise AcceptanceError(
                                f"SSE {phase} reached {event.event_type}{suffix} before "
                                f"{terminal_type}"
                            )
                        if event.event_type == terminal_type:
                            saw_terminal = True
                            break
                if saw_terminal:
                    return events
                reconnects += 1
            except (SseConnectionError, httpx.RequestError, httpx.StreamError):
                reconnects += 1
            finally:
                if response is not None:
                    response.close()
        raise AcceptanceError(
            f"SSE {phase} stream ended before {terminal_type} after bounded reconnects"
        )

    def _create_cleanup_status(self) -> str:
        if self.cleanup_status != "skipped_no_exact_delete_endpoint":
            return self.cleanup_status
        template = self.config.cleanup_endpoint_template
        if not template:
            return self.cleanup_status
        if self.session_id is None:
            return "skipped_no_session"
        try:
            path = template.format(session_id=self.session_id)
        except (IndexError, KeyError, ValueError):
            return "skipped_invalid_cleanup_endpoint"
        if not path.startswith("/") or "{" in path or "}" in path:
            return "skipped_invalid_cleanup_endpoint"
        try:
            response = self.api.request("DELETE", path)
        except (AcceptanceError, TypeError, ValueError):
            # Cleanup is best effort. Preserve the workflow report when a
            # user-supplied endpoint is unavailable or times out, and never
            # include transport details that could contain sensitive data.
            self.cleanup_status = "cleanup_request_failed"
        else:
            try:
                if response.status_code in {200, 202, 204}:
                    self.cleanup_status = "requested_and_accepted"
                else:
                    self.cleanup_status = f"delete_rejected_{response.status_code}"
            finally:
                response.close()
        return self.cleanup_status

    def verify(self) -> dict[str, Any]:
        checks: dict[str, bool] = {}
        report: dict[str, Any] = {
            "scope": "authenticated_http_current_sha_live_queue",
            "provider_request_budget": self.config.provider_request_budget,
            "budget_enforcement": (
                "preflight_and_postcondition_only; worker_dispatch_can_overshoot_before_observation"
            ),
            "cleanup": self.cleanup_status,
        }
        checks["bounded_no_worker_retries_requested"] = self.config.require_no_worker_retries
        try:
            health_response, health_body = self.api.json_request("GET", "/health")
            health = _object(health_body, "Health response")
            checks["health_ok"] = health_response.status_code == 200 and health.get("status") == "ok"
            checks["standard_mode"] = health.get("data_mode") == "standard"
            checks["v2_enabled"] = health.get("debate_workflow_v2") is True
            if "debate_queue_enabled" in health:
                checks["queue_enabled"] = health.get("debate_queue_enabled") is True
            server_sha = _extract_sha(health, health_response.headers)
            report["server_sha_present"] = server_sha is not None
            report["server_sha"] = server_sha
            if self.config.expected_sha:
                checks["current_sha"] = server_sha is not None and _sha_matches(self.config.expected_sha, server_sha)
            elif self.config.require_current_sha:
                checks["current_sha"] = False
                report["current_sha"] = "required_but_not_configured"
            else:
                checks["current_sha"] = True
                report["current_sha"] = "skipped_no_expected_sha"

            health_checks = {
                key: value
                for key, value in checks.items()
                if key in {"health_ok", "standard_mode", "v2_enabled", "queue_enabled", "current_sha"}
            }
            if not all(health_checks.values()):
                raise AcceptanceError("Health/current-SHA preflight failed; no Debate was admitted")

            idempotency_key = f"live-queue-{uuid4().hex[:24]}"
            create_response, create_body = self.api.json_request(
                "POST",
                "/debates",
                json_body={
                    "ticker": "AAPL",
                    "question": None,
                    "opening_side": "bull",
                    "idempotency_key": idempotency_key,
                },
                statuses={202},
            )
            create_detail = _object(create_body, "Queued Debate response")
            self.session_id = _session_id(create_detail)
            session = _object(create_detail.get("session"), "Queued Debate session")
            job = _object(create_detail.get("job"), "Queued Debate job")
            checks["queued_standard_aapl_admission"] = (
                create_response.status_code == 202
                and create_detail.get("execution_mode") == "queued"
                and session.get("ticker") == "AAPL"
                and session.get("status") == "queued_round_1"
                and job.get("job_type") == "round_1"
                and job.get("session_id") == self.session_id
            )
            initial_job_request_count = job.get("provider_request_count")
            checks["initial_budget_zero"] = isinstance(initial_job_request_count, int) and initial_job_request_count == 0
            worker_max_attempts = job.get("max_attempts")
            report["worker_max_attempts"] = worker_max_attempts
            if self.config.require_no_worker_retries:
                checks["worker_retry_policy"] = worker_max_attempts == 1

            round_one_events = self._stream_phase(
                after_sequence=0,
                terminal_type="session.awaiting_user",
                phase=1,
            )
            r1_event_check = _check_phase_events(round_one_events, phase=1)
            checks["round_one_sse_interim_judge"] = bool(r1_event_check["passed"] and r1_event_check["last_event"] == "session.awaiting_user")
            report["round_one_sse"] = r1_event_check
            round_one_cursor = round_one_events[-1].sequence

            r1_detail, r1_records = self._reload()
            r1_session = _object(r1_detail.get("session"), "Round 1 session")
            r1_messages = [_message(record) for record in r1_records]
            checks["round_one_durable_reload"] = (
                r1_session.get("status") == "awaiting_user"
                and len(r1_messages) == 7
                and r1_session.get("interim_judge_message_id") == r1_messages[-1].get("id")
                and r1_session.get("final_judge_message_id") is None
            )
            checks["round_one_role_counts"] = _role_counts(r1_messages) == {"bull": 3, "bear": 3, "judge": 1}
            checks["round_one_sequence"] = [message.get("sequence_number") for message in r1_messages] == list(range(1, 8))
            allowed = set()
            context = r1_session.get("analysis_context")
            if isinstance(context, dict) and isinstance(context.get("allowed_evidence_ids"), list):
                allowed = {str(item) for item in context["allowed_evidence_ids"]}
            if isinstance(context, dict):
                snapshot_ok, snapshot = _snapshot_summary(context)
            else:
                snapshot_ok, snapshot = False, {}
            checks["current_aapl_snapshot"] = snapshot_ok
            report["snapshot"] = snapshot
            citations_ok, citation_count = _check_citations(r1_records, allowed_evidence_ids=allowed)
            metadata_ok, metadata = _check_provider_metadata(r1_records)
            checks["round_one_citations"] = citations_ok
            checks["round_one_provider_metadata"] = metadata_ok
            checks["round_one_live_providers"] = _check_expected_providers(
                metadata,
                expected_turn_provider=self.config.expected_turn_provider,
                expected_judge_provider=self.config.expected_judge_provider,
            )
            report["round_one_citation_count"] = citation_count
            report["provider_models"] = metadata

            r1_by_id = _canonical_ids(r1_records)
            r1_audit = self._provider_attempts(r1_by_id)
            if self._provider_audit_available:
                r1_accounting = _check_attempts(
                    r1_audit,
                    phase=1,
                    expected_attempts=ROUND_ONE_PROVIDER_REQUESTS,
                    messages_by_id=r1_by_id,
                    budget=self.budget,
                    job=None,
                    require_single_attempt_per_message=self.config.require_no_worker_retries,
                )
            else:
                r1_accounting = {"passed": False, "skipped": True, "attempt_count": None}
                checks["provider_audit_available"] = self.config.allow_missing_provider_audit
            report["round_one_accounting"] = r1_accounting
            checks["round_one_usage_accounting"] = bool(r1_accounting.get("passed"))
            if self._provider_audit_available and not r1_accounting.get("passed"):
                raise AcceptanceError("Round 1 provider accounting did not match the canonical transcript")

            self.budget.require_room(ROUND_TWO_PROVIDER_REQUESTS)
            target = next(
                (message for message in r1_messages if message.get("role") == "bear"),
                None,
            )
            if target is None:
                raise AcceptanceError("Round 1 did not contain a Bear message to challenge")
            selected_text = str(target.get("content", ""))[:120]
            if not selected_text:
                raise AcceptanceError("Challenge target had no selectable text")
            challenge_response, challenge_body = self.api.json_request(
                "POST",
                f"/debates/{self.session_id}/interventions",
                json_body={
                    "selected_message_id": target.get("id"),
                    "selected_text": selected_text,
                    "question": DEFAULT_CHALLENGE,
                    "idempotency_key": f"challenge-{uuid4().hex[:24]}",
                },
                statuses={202},
            )
            challenge_detail = _object(challenge_body, "Queued Round 2 response")
            challenge_session = _object(challenge_detail.get("session"), "Queued Round 2 session")
            challenge_job = _object(challenge_detail.get("job"), "Queued Round 2 job")
            checks["queued_round_two_challenge"] = (
                challenge_response.status_code == 202
                and challenge_detail.get("execution_mode") == "queued"
                and challenge_session.get("status") == "queued_round_2"
                and challenge_job.get("job_type") == "round_2"
                and challenge_job.get("provider_request_count") == 0
                and any(
                    _message(record).get("role") == "user"
                    and _message(record).get("content") == DEFAULT_CHALLENGE
                    and _message(record).get("message_kind") == "question"
                    for record in _messages(challenge_detail)
                )
            )
            report["round_two_worker_max_attempts"] = challenge_job.get("max_attempts")
            if self.config.require_no_worker_retries:
                checks["round_two_worker_retry_policy"] = challenge_job.get("max_attempts") == 1

            round_two_events = self._stream_phase(
                after_sequence=round_one_cursor,
                terminal_type="session.completed",
                phase=2,
            )
            r2_event_check = _check_phase_events(round_two_events, phase=2)
            checks["round_two_sse_final_judge"] = bool(r2_event_check["passed"] and r2_event_check["last_event"] == "session.completed")
            report["round_two_sse"] = r2_event_check

            final_detail, final_records = self._reload()
            final_session = _object(final_detail.get("session"), "Final Debate session")
            final_messages = [_message(record) for record in final_records]
            checks["final_durable_reload"] = (
                final_session.get("status") == "completed"
                and len(final_messages) == 13
                and final_session.get("final_judge_message_id") == final_messages[-1].get("id")
            )
            checks["final_role_counts"] = _role_counts(final_messages) == {"bull": 5, "bear": 5, "judge": 2, "user": 1}
            checks["final_sequence"] = [message.get("sequence_number") for message in final_messages] == list(range(1, 14))
            final_allowed = set()
            final_context = final_session.get("analysis_context")
            if isinstance(final_context, dict) and isinstance(final_context.get("allowed_evidence_ids"), list):
                final_allowed = {str(item) for item in final_context["allowed_evidence_ids"]}
            final_citations_ok, final_citation_count = _check_citations(final_records, allowed_evidence_ids=final_allowed)
            final_metadata_ok, final_metadata = _check_provider_metadata(final_records)
            checks["final_citations"] = final_citations_ok
            checks["final_provider_metadata"] = final_metadata_ok
            checks["final_live_providers"] = _check_expected_providers(
                final_metadata,
                expected_turn_provider=self.config.expected_turn_provider,
                expected_judge_provider=self.config.expected_judge_provider,
            )
            report["final_citation_count"] = final_citation_count
            report["provider_models"] = final_metadata

            final_by_id = _canonical_ids(final_records)
            final_audit = self._provider_attempts(final_by_id)
            if self._provider_audit_available:
                final_accounting = _check_attempts(
                    final_audit,
                    phase=2,
                    expected_attempts=ROUND_TWO_PROVIDER_REQUESTS,
                    messages_by_id=final_by_id,
                    budget=self.budget,
                    job=None,
                    require_single_attempt_per_message=self.config.require_no_worker_retries,
                )
                checks["provider_audit_total"] = self.budget.observed >= 12
            else:
                final_accounting = {"passed": False, "skipped": True, "attempt_count": None}
            report["round_two_accounting"] = final_accounting
            checks["round_two_usage_accounting"] = bool(final_accounting.get("passed"))
            report["observed_provider_requests"] = self.budget.observed
            checks["provider_request_budget"] = self.budget.observed <= self.config.provider_request_budget
            report["sse_cursors"] = {"round_one_terminal": round_one_cursor, "round_two_terminal": round_two_events[-1].sequence}
        except (AcceptanceError, AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            report["error"] = str(exc)
            checks["workflow_error_free"] = False
            if self.session_id is not None:
                try:
                    failure_audit = self._provider_attempts({})
                    if self._provider_audit_available:
                        failure_accounting = _summarize_failure_attempts(
                            failure_audit,
                            budget=self.budget,
                        )
                        report["failure_provider_accounting"] = failure_accounting
                        checks["failure_provider_budget"] = (
                            self.budget.observed <= self.config.provider_request_budget
                        )
                except (
                    AcceptanceError,
                    AttributeError,
                    IndexError,
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    report["failure_provider_accounting"] = {
                        "available": False,
                    }
        finally:
            report["cleanup"] = self._create_cleanup_status()
            report["session_id"] = self.session_id
            report["observed_provider_requests"] = self.budget.observed
        report["checks"] = checks
        required_checks = [value for key, value in checks.items() if key != "current_sha" or self.config.require_current_sha or self.config.expected_sha]
        if not self._provider_audit_available and self.config.allow_missing_provider_audit:
            required_checks = [value for key, value in checks.items() if key not in {"provider_audit_available", "round_one_usage_accounting", "round_two_usage_accounting", "provider_audit_total"}]
        report["passed"] = bool(required_checks) and all(required_checks)
        return report


def verify_current_sha_live_queue(
    config: AcceptanceConfig,
    *,
    client: httpx.Client | None = None,
    client_factory: Callable[[], httpx.Client] | None = None,
) -> dict[str, Any]:
    """Run the acceptance workflow with a supplied authenticated HTTP client."""

    api = AuthenticatedApi(config, client=client, client_factory=client_factory)
    verifier = CurrentShaLiveQueueVerifier(api)
    try:
        return verifier.verify()
    finally:
        api.close()


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        "--api-url",
        dest="base_url",
        default=os.getenv("DEBATE_API_BASE_URL") or os.getenv("API_BASE_URL"),
    )
    parser.add_argument(
        "--token",
        "--access-token",
        dest="access_token",
        default=os.getenv("DEBATE_API_TOKEN") or os.getenv("API_TOKEN"),
        help="Bearer token (prefer DEBATE_API_TOKEN)",
    )
    parser.add_argument("--provider-request-budget", type=_positive_int, default=int(os.getenv("DEBATE_PROVIDER_REQUEST_BUDGET", str(DEFAULT_PROVIDER_REQUEST_BUDGET))))
    parser.add_argument(
        "--expected-sha",
        "--current-sha",
        dest="expected_sha",
        default=os.getenv("EXPECTED_CURRENT_SHA") or os.getenv("CURRENT_SHA"),
    )
    parser.add_argument(
        "--expected-turn-provider",
        default=os.getenv(
            "EXPECTED_DEBATE_TURN_PROVIDER",
            DEFAULT_EXPECTED_TURN_PROVIDER,
        ),
    )
    parser.add_argument(
        "--expected-judge-provider",
        default=os.getenv(
            "EXPECTED_DEBATE_JUDGE_PROVIDER",
            DEFAULT_EXPECTED_JUDGE_PROVIDER,
        ),
    )
    sha_group = parser.add_mutually_exclusive_group()
    sha_group.add_argument("--require-current-sha", dest="require_current_sha", action="store_true", default=True)
    sha_group.add_argument(
        "--allow-missing-current-sha",
        dest="require_current_sha",
        action="store_false",
        help="Allow a diagnostic run when the API does not expose a build SHA",
    )
    parser.add_argument(
        "--require-no-worker-retries",
        action="store_true",
        default=True,
        help="Require the queued Job response to advertise max_attempts=1",
    )
    parser.add_argument("--allow-missing-provider-audit", action="store_true")
    parser.add_argument("--max-reconnects", type=_nonnegative_int, default=DEFAULT_MAX_RECONNECTS)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_HTTP_TIMEOUT_SECONDS)
    parser.add_argument("--cleanup-endpoint", dest="cleanup_endpoint_template", default=None, help="Exact DELETE path template, e.g. /internal/acceptance/debates/{session_id}")
    args = parser.parse_args(argv)
    if not args.base_url:
        parser.error("--base-url or DEBATE_API_BASE_URL is required")
    if not args.access_token:
        parser.error("--token or DEBATE_API_TOKEN is required")
    return args


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    config = AcceptanceConfig(
        base_url=args.base_url,
        access_token=args.access_token,
        provider_request_budget=args.provider_request_budget,
        expected_sha=args.expected_sha,
        expected_turn_provider=args.expected_turn_provider,
        expected_judge_provider=args.expected_judge_provider,
        require_current_sha=args.require_current_sha,
        require_no_worker_retries=args.require_no_worker_retries,
        allow_missing_provider_audit=args.allow_missing_provider_audit,
        max_reconnects=args.max_reconnects,
        timeout_seconds=args.timeout_seconds,
        cleanup_endpoint_template=args.cleanup_endpoint_template,
    )
    report = verify_current_sha_live_queue(config)
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(0 if report.get("passed") else 1)


if __name__ == "__main__":
    main()
