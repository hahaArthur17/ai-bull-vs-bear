#!/usr/bin/env python3
"""Verify hosted Stop/interjection/Continue transactions with disposable rows.

The verifier uses the application's server-only repository, never calls a model,
archives the one Continue queue message, and deletes every temporary Session.
It also measures the network round trip of sequential draft checkpoints so the
per-delta persistence decision is based on the hosted project rather than the
local PostgreSQL benchmark alone.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import json
import math
import time
from uuid import UUID, uuid4

import httpx

from app.config import get_settings
from app.domain.debate import DebateDraftCheckpoint, DebateSession, ProviderAttempt
from app.domain.factors import AnalysisContext, FactorSnapshot
from app.domain.jobs import DebateJob
from app.repositories.debate_repository import (
    DebateConcurrencyError,
    DebateRepositoryError,
)
from app.repositories.supabase_debate_repository import SupabaseDebateRepository
from app.services.debate_interruption import prepare_continuation, prepare_interjection
from app.services.debate_state import transition_session

try:
    from scripts.verify_supabase_debate_persistence import (
        AuthSession,
        HostedDebatePersistenceVerifier,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    from verify_supabase_debate_persistence import (
        AuthSession,
        HostedDebatePersistenceVerifier,
    )


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


def latency_summary(values: list[float]) -> dict[str, float]:
    return {
        "p50_ms": round(percentile(values, 0.50), 3),
        "p95_ms": round(percentile(values, 0.95), 3),
        "mean_ms": round(sum(values) / len(values), 3),
        "min_ms": round(min(values), 3),
        "max_ms": round(max(values), 3),
    }


class HostedDebateInterruptionVerifier:
    AUTHENTICATED_RPC_PAYLOADS: dict[str, dict[str, object]] = {
        "rpc/checkpoint_debate_draft": {"message_payload": {}},
        "rpc/interrupt_debate_generation": {
            "requested_session_id": str(UUID(int=0)),
            "requested_user_id": str(UUID(int=0)),
            "requested_generation_id": str(UUID(int=0)),
            "requested_message_id": str(UUID(int=0)),
            "visible_prefix": "",
            "interrupted_at": "2026-09-11T00:00:00+00:00",
        },
        "rpc/record_debate_interjection": {"message_payload": {}},
        "rpc/continue_interrupted_debate": {
            "session_payload": {},
            "job_payload": {},
            "queue_payload": {},
            "expected_generation_id": str(UUID(int=0)),
            "requested_interjection_id": str(UUID(int=0)),
        },
        "rpc/interrupt_debate_before_output_generation": {
            "requested_session_id": str(UUID(int=0)),
            "requested_user_id": str(UUID(int=0)),
            "requested_generation_id": str(UUID(int=0)),
            "interrupted_at": "2026-09-11T00:00:00+00:00",
        },
        "rpc/admit_debate_provider_attempt": {
            "attempt_payload": {},
            "checkpoint_payload": {},
        },
        "rpc/dispatch_debate_provider_attempt": {
            "requested_attempt_id": str(UUID(int=0)),
            "dispatched_at": "2026-09-11T00:00:00+00:00",
        },
        "rpc/finish_debate_provider_attempt": {
            "requested_attempt_id": str(UUID(int=0)),
            "finished_at": "2026-09-11T00:00:00+00:00",
        },
    }

    def __init__(
        self,
        supabase_url: str,
        anon_key: str,
        secret_key: str,
        *,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        if not supabase_url.strip() or not anon_key.strip() or not secret_key.strip():
            raise ValueError("Hosted interruption verification requires Supabase credentials")
        self.supabase_url = supabase_url.rstrip("/")
        self.anon_key = anon_key
        self.secret_key = secret_key
        self.client_factory = client_factory or (lambda: httpx.Client(timeout=15.0))
        self.clients: list[httpx.Client] = []
        self.control_client = self._new_client()
        self.persistence = HostedDebatePersistenceVerifier(
            self.supabase_url,
            self.anon_key,
            self.secret_key,
            self.control_client,
        )

    def sign_in(self, email: str, password: str) -> AuthSession:
        return self.persistence.sign_in(email, password)

    def stock_id(self) -> int:
        return self.persistence.stock_id()

    def verify(
        self,
        user_a: AuthSession,
        user_b: AuthSession,
        stock_id: int,
        *,
        checkpoint_samples: int = 24,
    ) -> dict[str, object]:
        if not 2 <= checkpoint_samples <= 120:
            raise ValueError("checkpoint_samples must be between 2 and 120")
        session_ids: list[UUID] = []
        queue_message_ids: list[int] = []
        report: dict[str, object] = {}
        try:
            visible = self._visible_prefix_flow(
                user_a,
                user_b,
                stock_id,
                checkpoint_samples,
                session_ids,
                queue_message_ids,
            )
            before_output = self._before_output_flow(user_b, stock_id, session_ids)
            checks = {
                **visible["checks"],
                **before_output["checks"],
                "authenticated_interruption_rpcs_rejected": (
                    self._authenticated_rpcs_rejected(user_a)
                ),
            }
            report = {
                "checks": checks,
                "checkpoint_latency_ms": visible["checkpoint_latency_ms"],
                "checkpoint_samples": checkpoint_samples,
            }
            if not all(checks.values()):
                raise RuntimeError(f"Hosted interruption checks failed: {checks}")
        finally:
            try:
                archive_results = [
                    self._repository().archive_job_message(message_id)
                    for message_id in queue_message_ids
                ]
            finally:
                cleanup_removed = (
                    self.persistence._cleanup_sessions(tuple(session_ids))
                    if session_ids
                    else True
                )
                for client in self.clients:
                    client.close()

        report["cleanup"] = {
            "queue_messages_archived": bool(queue_message_ids)
            and all(archive_results),
            "sessions_removed": cleanup_removed,
        }
        if not all(report["cleanup"].values()):
            raise RuntimeError(f"Hosted interruption cleanup failed: {report['cleanup']}")
        return report

    def _visible_prefix_flow(
        self,
        owner: AuthSession,
        other: AuthSession,
        stock_id: int,
        samples: int,
        session_ids: list[UUID],
        queue_message_ids: list[int],
    ) -> dict[str, object]:
        repository = self._repository()
        running, original_job = self._create_running_session(
            repository,
            owner.user_id,
            stock_id,
        )
        session_ids.append(running.id)
        message_id = uuid4()
        checkpoint = DebateDraftCheckpoint(
            message_id=message_id,
            session_id=running.id,
            branch_id=running.active_branch_id,
            generation_id=running.active_generation_id,
            sequence_number=1,
            round_number=1,
            exchange_number=1,
            role="bull",
            message_kind="argument",
            content="",
            created_at=running.updated_at,
        )
        admitted_at = datetime.now(timezone.utc)
        attempt = ProviderAttempt(
            id=uuid4(),
            session_id=running.id,
            generation_id=running.active_generation_id,
            message_id=message_id,
            role="bull",
            provider="hosted-verifier",
            model="no-model-call",
            admitted_at=admitted_at,
        )
        admitted = repository.admit_provider_attempt(attempt, checkpoint)
        dispatched = repository.mark_provider_attempt_dispatched(
            attempt.id,
            admitted_at + timedelta(milliseconds=1),
        )

        latencies: list[float] = []
        content = ""
        for index in range(1, samples + 1):
            content += f"d{index:03d}:hosted-checkpoint "
            current = checkpoint.model_copy(update={"content": content})
            started = time.perf_counter()
            repository.checkpoint_draft(current)
            latencies.append((time.perf_counter() - started) * 1000)

        wrong_owner_rejected = self._rejects_concurrently(
            lambda: self._repository().interrupt_generation(
                running.id,
                other.user_id,
                running.active_generation_id,
                message_id,
                content,
                datetime.now(timezone.utc),
            )
        )
        stopped = repository.interrupt_generation(
            running.id,
            running.user_id,
            running.active_generation_id,
            message_id,
            content,
            datetime.now(timezone.utc),
        )
        replayed_stop = repository.interrupt_generation(
            running.id,
            running.user_id,
            running.active_generation_id,
            message_id,
            content,
            datetime.now(timezone.utc),
        )
        finished = repository.finish_provider_attempt(
            attempt.id,
            at=datetime.now(timezone.utc),
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        )

        recovered_repository = self._repository()
        recovered = recovered_repository.get_session(stopped.id, stopped.user_id)
        recovered_messages = recovered_repository.list_messages(
            stopped.id,
            stopped.user_id,
            branch_id=stopped.active_branch_id,
        )
        recovered_attempts = recovered_repository.list_provider_attempts(
            stopped.id,
            stopped.user_id,
        )
        stale_message_id = uuid4()
        stale_attempt_rejected = self._rejects_concurrently(
            lambda: recovered_repository.admit_provider_attempt(
                attempt.model_copy(update={"id": uuid4(), "message_id": stale_message_id}),
                checkpoint.model_copy(update={"message_id": stale_message_id}),
            )
        )

        assert recovered is not None
        point = prepare_interjection(
            recovered,
            recovered_messages,
            expected_generation_id=recovered.active_generation_id,
            content="Please distinguish the partial premise from any missing conclusion.",
            idempotency_key=f"hosted-interject-{uuid4().hex}",
            at=datetime.now(timezone.utc),
        )
        stored_point = recovered_repository.record_interjection(point)
        replayed_point = recovered_repository.record_interjection(point)
        no_job_after_interjection = (
            recovered_repository.get_active_job(recovered.id, recovered.user_id) is None
        )
        waiting = recovered_repository.get_session(recovered.id, recovered.user_id)
        transcript = recovered_repository.list_messages(
            recovered.id,
            recovered.user_id,
            branch_id=recovered.active_branch_id,
        )
        assert waiting is not None
        queued, continuation_job, envelope = prepare_continuation(
            waiting,
            transcript,
            expected_generation_id=waiting.active_generation_id,
            interjection_id=point.id,
            idempotency_key=f"hosted-continue-{uuid4().hex}",
            at=datetime.now(timezone.utc),
            max_attempts=1,
        )
        continued, queued_job = recovered_repository.continue_interrupted(
            queued,
            continuation_job,
            envelope,
            expected_generation_id=waiting.active_generation_id,
            interjection_id=point.id,
        )
        replayed_continue = recovered_repository.continue_interrupted(
            queued,
            continuation_job,
            envelope,
            expected_generation_id=waiting.active_generation_id,
            interjection_id=point.id,
        )
        final_repository = self._repository()
        final_session = final_repository.get_session(continued.id, continued.user_id)
        final_messages = final_repository.list_messages(
            continued.id,
            continued.user_id,
            branch_id=continued.active_branch_id,
        )
        final_attempts = final_repository.list_provider_attempts(
            continued.id,
            continued.user_id,
        )
        if queued_job.queue_message_id is None:
            raise RuntimeError("Hosted Continue returned no Queue message identifier")
        queue_message_ids.append(queued_job.queue_message_id)
        checks = {
            "provider_attempt_admitted_and_dispatched": (
                admitted == attempt and dispatched.outcome == "dispatched"
            ),
            "wrong_owner_stop_rejected": wrong_owner_rejected,
            "visible_prefix_stop_is_exact_and_idempotent": (
                stopped == replayed_stop
                and stopped.status == "interrupted_awaiting_user"
                and len(recovered_messages) == 1
                and recovered_messages[0].content == content
                and not recovered_messages[0].is_complete
                and recovered_messages[0].metadata.get("interrupted") is True
                and recovered_repository.list_message_evidence(message_id, owner.user_id) == ()
            ),
            "late_attempt_usage_survives_stop": (
                finished.outcome == "completed"
                and finished.usage_status == "reported"
                and finished.total_tokens == 18
                and recovered_attempts == [finished]
            ),
            "restart_recovers_waiting_state": recovered == stopped,
            "old_generation_admission_rejected": stale_attempt_rejected,
            "interjection_is_idempotent_without_queue_admission": (
                stored_point == replayed_point == point and no_job_after_interjection
            ),
            "continue_is_atomic_idempotent_and_snapshot_stable": (
                replayed_continue == (continued, queued_job)
                and final_session == continued
                and continued.status == "queued_round_1"
                and continued.active_generation_id != stopped.active_generation_id
                and continued.analysis_context == stopped.analysis_context
                and continued.factor_snapshot == stopped.factor_snapshot
                and queued_job.status == "queued"
                and queued_job.max_attempts == 1
                and len(final_messages) == 2
                and final_attempts == [finished]
            ),
        }
        return {
            "session_id": running.id,
            "queue_message_id": queued_job.queue_message_id,
            "checkpoint_latency_ms": latency_summary(latencies),
            "checks": checks,
            "original_job_id": original_job.id,
        }

    def _before_output_flow(
        self,
        owner: AuthSession,
        stock_id: int,
        session_ids: list[UUID],
    ) -> dict[str, object]:
        repository = self._repository()
        queued, job = self._create_queued_session(repository, owner.user_id, stock_id)
        session_ids.append(queued.id)
        stopped = repository.interrupt_before_output_generation(
            queued.id,
            queued.user_id,
            queued.active_generation_id,
            datetime.now(timezone.utc),
        )
        replayed = repository.interrupt_before_output_generation(
            queued.id,
            queued.user_id,
            queued.active_generation_id,
            datetime.now(timezone.utc),
        )
        recovered_repository = self._repository()
        recovered = recovered_repository.get_session(stopped.id, stopped.user_id)
        messages = recovered_repository.list_messages(
            stopped.id,
            stopped.user_id,
            branch_id=stopped.active_branch_id,
        )
        stored_job = recovered_repository.get_job(job.id)
        return {
            "session_id": queued.id,
            "checks": {
                "before_output_stop_is_empty_idempotent_and_recoverable": (
                    replayed == stopped
                    and recovered == stopped
                    and len(messages) == 1
                    and messages[0].id == queued.active_generation_id
                    and messages[0].content == ""
                    and not messages[0].is_complete
                    and messages[0].metadata
                    == {"interrupted": True, "before_output": True}
                    and stored_job is not None
                    and stored_job.status == "cancelled"
                )
            },
        }

    def _create_running_session(
        self,
        repository: SupabaseDebateRepository,
        user_id: UUID,
        stock_id: int,
    ) -> tuple[DebateSession, DebateJob]:
        queued, job = self._create_queued_session(repository, user_id, stock_id)
        running = transition_session(
            queued,
            "running_round_1",
            at=max(datetime.now(timezone.utc), queued.updated_at),
        )
        return repository.update_session(running, expected_status="queued_round_1"), job

    @staticmethod
    def _create_queued_session(
        repository: SupabaseDebateRepository,
        user_id: UUID,
        stock_id: int,
    ) -> tuple[DebateSession, DebateJob]:
        created_at = datetime.now(timezone.utc)
        session = DebateSession(
            id=uuid4(),
            user_id=user_id,
            stock_id=stock_id,
            ticker="AAPL",
            mode="demo",
            opening_side="bull",
            active_branch_id=uuid4(),
            active_generation_id=uuid4(),
            analysis_context=AnalysisContext(
                ticker="AAPL",
                as_of=created_at.isoformat(),
                captured_at=created_at,
            ),
            factor_snapshot=FactorSnapshot(ticker="AAPL", as_of=created_at.isoformat()),
            created_at=created_at,
            updated_at=created_at,
        )
        job = DebateJob(
            id=uuid4(),
            session_id=session.id,
            user_id=user_id,
            job_type="round_1",
            idempotency_key=f"hosted-interruption-{uuid4().hex}",
            max_attempts=1,
            available_at=created_at,
            created_at=created_at,
            updated_at=created_at,
        )
        repository.create_session_with_job(session, job)
        queued = transition_session(
            session,
            "queued_round_1",
            at=created_at + timedelta(milliseconds=1),
        )
        return repository.update_session(queued, expected_status="created"), job

    def _authenticated_rpcs_rejected(self, session: AuthSession) -> bool:
        denied = {401, 403, 404}
        return all(
            self.persistence._authenticated_request(
                "POST",
                path,
                session,
                json=payload,
            ).status_code
            in denied
            for path, payload in self.AUTHENTICATED_RPC_PAYLOADS.items()
        )

    @staticmethod
    def _rejects_concurrently(call: Callable[[], object]) -> bool:
        for attempt_number in range(2):
            try:
                call()
            except DebateConcurrencyError:
                return True
            except DebateRepositoryError:
                if attempt_number == 1:
                    raise
        return False

    def _repository(self) -> SupabaseDebateRepository:
        return SupabaseDebateRepository(
            self.supabase_url,
            self.secret_key,
            self._new_client(),
        )

    def _new_client(self) -> httpx.Client:
        client = self.client_factory()
        self.clients.append(client)
        return client


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify hosted Supabase Debate interruption transactions."
    )
    parser.add_argument(
        "--checkpoint-samples",
        type=int,
        default=24,
        help="Sequential hosted checkpoint calls to measure (2-120; default: 24).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()
    required = {
        "SUPABASE_URL": settings.supabase_url,
        "SUPABASE_ANON_KEY": settings.supabase_anon_key,
        "SUPABASE_SECRET_KEY": settings.supabase_secret_key,
        "SUPABASE_RLS_USER_A_EMAIL": settings.supabase_rls_user_a_email,
        "SUPABASE_RLS_USER_A_PASSWORD": settings.supabase_rls_user_a_password,
        "SUPABASE_RLS_USER_B_EMAIL": settings.supabase_rls_user_b_email,
        "SUPABASE_RLS_USER_B_PASSWORD": settings.supabase_rls_user_b_password,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    verifier = HostedDebateInterruptionVerifier(
        str(settings.supabase_url),
        str(settings.supabase_anon_key),
        str(settings.supabase_secret_key),
    )
    user_a = verifier.sign_in(
        str(settings.supabase_rls_user_a_email),
        str(settings.supabase_rls_user_a_password),
    )
    user_b = verifier.sign_in(
        str(settings.supabase_rls_user_b_email),
        str(settings.supabase_rls_user_b_password),
    )
    report = verifier.verify(
        user_a,
        user_b,
        verifier.stock_id(),
        checkpoint_samples=args.checkpoint_samples,
    )
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
