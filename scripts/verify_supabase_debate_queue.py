#!/usr/bin/env python3
"""Verify hosted pgmq Debate transport with disposable deterministic jobs."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import json
from uuid import UUID, uuid4

import httpx

from app.config import get_settings
from app.domain.debate import DebateSession
from app.domain.factors import AnalysisContext, FactorSnapshot
from app.domain.jobs import DebateJob, DebateQueueMessage
from app.providers.deterministic_debate import DeterministicDebateProvider
from app.repositories.supabase_debate_repository import SupabaseDebateRepository
from app.services.debate_job_state import start_job
from app.services.debate_preview import DebatePreviewService
from app.services.debate_state import transition_session
from app.services.debate_worker import DebateWorker

try:
    from scripts.verify_supabase_debate_persistence import (
        AuthSession,
        HostedDebatePersistenceVerifier,
    )
except ModuleNotFoundError:  # Direct `python scripts/...` execution.
    from verify_supabase_debate_persistence import (
        AuthSession,
        HostedDebatePersistenceVerifier,
    )


class HostedDebateQueueVerifier:
    QUEUE_RPC_PAYLOADS: dict[str, dict[str, object]] = {
        "rpc/enqueue_debate_session_job": {
            "session_payload": {},
            "job_payload": {},
            "queue_payload": {},
        },
        "rpc/enqueue_debate_round_two": {
            "intervention_payload": {},
            "question_payload": {},
            "session_payload": {},
            "job_payload": {},
            "queue_payload": {},
        },
        "rpc/claim_debate_job": {"visibility_timeout_seconds": 30},
        "rpc/archive_debate_job": {"queue_message_id": 1},
        "rpc/retry_debate_job": {"queue_message_id": 1, "delay_seconds": 0},
        "rpc/requeue_debate_job": {
            "debate_job_id": str(UUID(int=0)),
            "expected_attempt_count": 1,
            "observed_provider_request_count": 0,
            "observed_prompt_tokens": 0,
            "observed_completion_tokens": 0,
        },
        "rpc/fail_exhausted_debate_job": {
            "debate_job_id": str(UUID(int=0)),
            "expected_attempt_count": 1,
        },
    }

    def __init__(
        self,
        supabase_url: str,
        anon_key: str,
        secret_key: str,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.anon_key = anon_key
        self.secret_key = secret_key
        self.client_factory = client_factory or (lambda: httpx.Client(timeout=15.0))
        self.clients: list[httpx.Client] = []
        self.auth_client = self._new_client()
        self.persistence_verifier = HostedDebatePersistenceVerifier(
            self.supabase_url,
            self.anon_key,
            self.secret_key,
            self.auth_client,
        )
        self.queue_message_ids: list[int] = []

    def sign_in(self, email: str, password: str) -> AuthSession:
        return self.persistence_verifier.sign_in(email, password)

    def stock_id(self) -> int:
        return self.persistence_verifier.stock_id()

    def verify(
        self,
        user_a: AuthSession,
        user_b: AuthSession,
        stock_id: int,
    ) -> dict[str, bool]:
        session_ids: list[UUID] = []
        report: dict[str, bool] = {}
        try:
            two_round = self._verify_two_round_worker(user_a, stock_id)
            session_ids.append(two_round["session_id"])
            report.update(two_round["checks"])

            recovered = self._verify_restart_recovery(user_b, stock_id)
            session_ids.append(recovered["session_id"])
            report.update(recovered["checks"])

            exhausted = self._verify_exhausted_failure(user_b, stock_id)
            session_ids.append(exhausted["session_id"])
            report.update(exhausted["checks"])

            report["authenticated_queue_rpcs_rejected"] = (
                self._authenticated_queue_rpcs_rejected(user_a)
            )
        finally:
            report["canonical_cleanup_removed"] = (
                self.persistence_verifier._cleanup_sessions(tuple(session_ids))
                if session_ids
                else True
            )
            for client in self.clients:
                client.close()

        if not all(report.values()):
            raise RuntimeError(
                "Hosted Debate Queue verification failed: "
                f"{report}; queue_message_ids={self.queue_message_ids}"
            )
        return report

    def _verify_two_round_worker(
        self,
        user: AuthSession,
        stock_id: int,
    ) -> dict[str, object]:
        repository, preview, _ = self._new_runtime()
        as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        context = AnalysisContext(ticker="AAPL", as_of=as_of)
        snapshot = FactorSnapshot(ticker="AAPL", as_of=as_of)
        idempotency_key = f"hosted-queue-round-one-{uuid4()}"
        queued, queued_job = preview.create_queued_round_one(
            user_id=user.user_id,
            stock_id=stock_id,
            ticker="AAPL",
            opening_side="bull",
            question=None,
            idempotency_key=idempotency_key,
            analysis_context=context,
            factor_snapshot=snapshot,
        )
        repeated = preview.create_queued_round_one(
            user_id=user.user_id,
            stock_id=stock_id,
            ticker="AAPL",
            opening_side="bull",
            question=None,
            idempotency_key=idempotency_key,
            analysis_context=context,
            factor_snapshot=snapshot,
        )
        if queued_job.queue_message_id is None:
            raise RuntimeError("Hosted Queue admission returned no message identifier")
        self.queue_message_ids.append(queued_job.queue_message_id)

        unbound_job = DebateJob.model_validate(
            {**queued_job.model_dump(mode="python"), "queue_message_id": None}
        )
        queue_payload = DebateQueueMessage(
            job_id=unbound_job.id,
            session_id=queued.id,
            job_type=unbound_job.job_type,
            trace_id=f"trace_{unbound_job.id.hex}",
            enqueued_at=unbound_job.created_at,
        )
        database_replay = repository.create_session_with_job_and_enqueue(
            queued,
            unbound_job,
            queue_payload,
        )

        restarted_repository, restarted_preview, round_one_worker = self._new_runtime()
        round_one_result = asyncio.run(round_one_worker.run_once())
        awaiting = restarted_repository.get_session(queued.id, user.user_id)
        messages = restarted_repository.list_messages(
            queued.id,
            user.user_id,
            branch_id=queued.active_branch_id,
        )
        completed_round_one_job = restarted_repository.get_job(queued_job.id)
        if awaiting is None or not messages:
            raise RuntimeError("Hosted Queue Round 1 did not persist canonical state")

        target = messages[-1]
        round_two_key = f"hosted-queue-round-two-{uuid4()}"
        queued_round_two, round_two_job = restarted_preview.create_queued_round_two(
            session=awaiting,
            selected_message_id=target.id,
            selected_text=target.content[:80],
            question="Which missing evidence could change this assessment?",
            idempotency_key=round_two_key,
        )
        repeated_round_two = restarted_preview.create_queued_round_two(
            session=awaiting,
            selected_message_id=target.id,
            selected_text=target.content[:80],
            question="Which missing evidence could change this assessment?",
            idempotency_key=round_two_key,
        )
        if round_two_job.queue_message_id is None:
            raise RuntimeError("Hosted Queue Round 2 returned no message identifier")
        self.queue_message_ids.append(round_two_job.queue_message_id)

        final_repository, _, round_two_worker = self._new_runtime()
        round_two_result = asyncio.run(round_two_worker.run_once())
        completed = final_repository.get_session(queued.id, user.user_id)
        completed_round_two_job = final_repository.get_job(round_two_job.id)
        final_messages = final_repository.list_messages(
            queued.id,
            user.user_id,
            branch_id=queued.active_branch_id,
        )
        idle = asyncio.run(round_two_worker.run_once())

        checks = {
            "atomic_round_one_admission_idempotent": (
                repeated == (queued, queued_job)
                and database_replay == (queued, queued_job)
            ),
            "restarted_worker_completed_round_one": (
                round_one_result.outcome == "completed"
                and round_one_result.read_count == 1
                and awaiting.status == "awaiting_user"
                and completed_round_one_job is not None
                and completed_round_one_job.status == "completed"
                and len(messages) == 7
            ),
            "atomic_round_two_admission_idempotent": repeated_round_two == (
                queued_round_two,
                round_two_job,
            ),
            "round_two_worker_completed": round_two_result.outcome == "completed",
            "round_two_first_delivery": round_two_result.read_count == 1,
            "round_two_session_completed": (
                completed is not None and completed.status == "completed"
            ),
            "round_two_job_completed": (
                completed_round_two_job is not None
                and completed_round_two_job.status == "completed"
            ),
            "round_two_transcript_complete": (
                len(final_messages) == len({message.id for message in final_messages}) == 13
            ),
            "queue_idle_after_round_two": idle.outcome == "idle",
        }
        return {"session_id": queued.id, "checks": checks}

    def _verify_restart_recovery(
        self,
        user: AuthSession,
        stock_id: int,
    ) -> dict[str, object]:
        repository, preview, _ = self._new_runtime()
        as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        queued, queued_job = preview.create_queued_round_one(
            user_id=user.user_id,
            stock_id=stock_id,
            ticker="AAPL",
            opening_side="bear",
            question=None,
            idempotency_key=f"hosted-queue-recovery-{uuid4()}",
            analysis_context=AnalysisContext(ticker="AAPL", as_of=as_of),
            factor_snapshot=FactorSnapshot(ticker="AAPL", as_of=as_of),
        )
        if queued_job.queue_message_id is None:
            raise RuntimeError("Hosted recovery admission returned no Queue message")
        self.queue_message_ids.append(queued_job.queue_message_id)
        first_claim = repository.claim_job(visibility_timeout_seconds=30)
        if first_claim is None:
            raise RuntimeError("Hosted recovery fixture could not be claimed")

        started_at = max(datetime.now(timezone.utc), queued_job.updated_at)
        running_job = start_job(queued_job, at=started_at)
        repository.update_job(running_job, expected_status="queued")
        running_session = transition_session(
            queued,
            "running_round_1",
            at=max(started_at, queued.updated_at),
        )
        repository.update_session(running_session, expected_status="queued_round_1")
        visibility_released = repository.retry_job_message(
            first_claim.queue_message_id,
            delay_seconds=0,
        )

        recovered_repository, _, recovered_worker = self._new_runtime()
        recovered_result = asyncio.run(recovered_worker.run_once())
        recovered_session = recovered_repository.get_session(queued.id, user.user_id)
        recovered_job = recovered_repository.get_job(queued_job.id)
        recovered_messages = recovered_repository.list_messages(
            queued.id,
            user.user_id,
            branch_id=queued.active_branch_id,
        )
        checks = {
            "visibility_retry_released_message": visibility_released,
            "fresh_worker_recovered_running_job": (
                first_claim.read_count == 1
                and recovered_result.outcome == "completed"
                and recovered_result.read_count == 2
                and recovered_session is not None
                and recovered_session.status == "awaiting_user"
                and recovered_job is not None
                and recovered_job.status == "completed"
                and recovered_job.attempt_count == 2
                and len(recovered_messages) == 7
            ),
        }
        return {"session_id": queued.id, "checks": checks}

    def _verify_exhausted_failure(
        self,
        user: AuthSession,
        stock_id: int,
    ) -> dict[str, object]:
        repository, _, _ = self._new_runtime()
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        fixture = HostedDebatePersistenceVerifier._build_fixture(
            user.user_id,
            stock_id,
            created_at,
            "queue-exhausted",
        )
        queued_at = created_at + timedelta(seconds=1)
        queued_session = transition_session(
            fixture.session,
            "queued_round_1",
            at=queued_at,
        )
        queued_job = DebateJob.model_validate(
            {
                **fixture.job.model_dump(mode="python"),
                "max_attempts": 1,
                "available_at": queued_at,
                "created_at": queued_at,
                "updated_at": queued_at,
            }
        )
        queue_payload = DebateQueueMessage(
            job_id=queued_job.id,
            session_id=queued_session.id,
            job_type=queued_job.job_type,
            trace_id=f"trace_{queued_job.id.hex}",
            enqueued_at=queued_at,
        )
        _, admitted_job = repository.create_session_with_job_and_enqueue(
            queued_session,
            queued_job,
            queue_payload,
        )
        if admitted_job.queue_message_id is None:
            raise RuntimeError("Hosted exhausted fixture returned no Queue message")
        self.queue_message_ids.append(admitted_job.queue_message_id)
        claimed = repository.claim_job(visibility_timeout_seconds=30)
        if claimed is None:
            raise RuntimeError("Hosted exhausted fixture could not be claimed")
        started_at = queued_at + timedelta(seconds=1)
        running_job = start_job(admitted_job, at=started_at)
        repository.update_job(running_job, expected_status="queued")
        running_session = transition_session(
            queued_session,
            "running_round_1",
            at=started_at,
        )
        repository.update_session(running_session, expected_status="queued_round_1")
        failed_session, failed_job = repository.fail_exhausted_job(
            admitted_job.id,
            expected_attempt_count=1,
        )
        archived = repository.archive_job_message(claimed.queue_message_id)
        checks = {
            "exhausted_retry_terminalized": (
                failed_session.status == "failed"
                and failed_session.safe_error_code == "debate_retry_exhausted"
                and failed_job.status == "failed"
                and failed_job.safe_error_code == "debate_retry_exhausted"
                and archived
            )
        }
        return {"session_id": queued_session.id, "checks": checks}

    def _authenticated_queue_rpcs_rejected(self, session: AuthSession) -> bool:
        denied = {401, 403, 404}
        return all(
            self.persistence_verifier._authenticated_request(
                "POST",
                path,
                session,
                json=payload,
            ).status_code
            in denied
            for path, payload in self.QUEUE_RPC_PAYLOADS.items()
        )

    def _new_runtime(
        self,
    ) -> tuple[SupabaseDebateRepository, DebatePreviewService, DebateWorker]:
        client = self._new_client()
        repository = SupabaseDebateRepository(
            self.supabase_url,
            self.secret_key,
            client,
        )
        provider = DeterministicDebateProvider()
        preview = DebatePreviewService(repository, provider, provider)
        worker = DebateWorker(
            repository,
            repository,
            preview.orchestrator,
            visibility_timeout_seconds=30,
        )
        return repository, preview, worker

    def _new_client(self) -> httpx.Client:
        client = self.client_factory()
        self.clients.append(client)
        return client


def main() -> None:
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

    verifier = HostedDebateQueueVerifier(
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
    checks = verifier.verify(user_a, user_b, verifier.stock_id())
    print(
        json.dumps(
            {
                "checks": checks,
                "queue_message_ids_for_sql_cleanup": sorted(
                    set(verifier.queue_message_ids)
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
