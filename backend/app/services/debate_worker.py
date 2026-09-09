from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Literal
from uuid import UUID

from app.repositories.debate_repository import (
    DebateQueueRepository,
    DebateRepositoryError,
    DebateUnitOfWork,
)
from app.services.debate_job_state import cancel_job
from app.services.debate_orchestrator import (
    DebateOrchestrationError,
    DebateOrchestrator,
    DebateRetryableOrchestrationError,
)


logger = logging.getLogger(__name__)


DebateWorkerOutcome = Literal[
    "idle",
    "completed",
    "cancelled",
    "failed",
    "skipped_terminal",
    "deferred_running",
    "retry_scheduled",
    "invalid",
]


@dataclass(frozen=True)
class DebateWorkerResult:
    outcome: DebateWorkerOutcome
    queue_message_id: int | None = None
    job_id: UUID | None = None
    read_count: int = 0
    retry_delay_seconds: int | None = None


class DebateWorker:
    """One bounded pull consumer for durable Debate stage messages."""

    def __init__(
        self,
        repository: DebateUnitOfWork,
        queue: DebateQueueRepository,
        orchestrator: DebateOrchestrator,
        *,
        visibility_timeout_seconds: int = 900,
    ) -> None:
        if not 30 <= visibility_timeout_seconds <= 3600:
            raise ValueError("Worker visibility timeout is outside safe bounds")
        self.repository = repository
        self.queue = queue
        self.orchestrator = orchestrator
        self.visibility_timeout_seconds = visibility_timeout_seconds

    async def run_once(self) -> DebateWorkerResult:
        claimed = await asyncio.to_thread(
            self.queue.claim_job,
            visibility_timeout_seconds=self.visibility_timeout_seconds,
        )
        if claimed is None:
            return DebateWorkerResult(outcome="idle")

        queue_message_id = claimed.queue_message_id
        payload = claimed.payload
        job = await asyncio.to_thread(self.repository.get_job, payload.job_id)
        if job is None:
            await self._archive(queue_message_id)
            return DebateWorkerResult(
                outcome="invalid",
                queue_message_id=queue_message_id,
                job_id=payload.job_id,
                read_count=claimed.read_count,
            )
        session = await asyncio.to_thread(
            self.repository.get_session,
            payload.session_id,
            job.user_id,
        )
        if (
            session is None
            or job.session_id != payload.session_id
            or job.job_type != payload.job_type
            or job.queue_message_id != queue_message_id
        ):
            await self._archive(queue_message_id)
            return DebateWorkerResult(
                outcome="invalid",
                queue_message_id=queue_message_id,
                job_id=job.id,
                read_count=claimed.read_count,
            )

        if job.status in {"completed", "cancelled", "failed"}:
            if job.status == "cancelled" and session.status == "cancel_requested":
                await asyncio.to_thread(
                    self.orchestrator.request_cancellation,
                    session.id,
                    session.user_id,
                    session.active_generation_id,
                )
            await self._archive(queue_message_id)
            return DebateWorkerResult(
                outcome=(
                    "cancelled" if job.status == "cancelled" else "skipped_terminal"
                ),
                queue_message_id=queue_message_id,
                job_id=job.id,
                read_count=claimed.read_count,
            )
        if session.status == "cancel_requested" and job.status == "queued":
            await asyncio.to_thread(
                self.orchestrator.request_cancellation,
                session.id,
                session.user_id,
                session.active_generation_id,
            )
            await self._archive(queue_message_id)
            return DebateWorkerResult(
                outcome="cancelled",
                queue_message_id=queue_message_id,
                job_id=job.id,
                read_count=claimed.read_count,
            )
        if job.status == "running":
            if claimed.read_count <= 1:
                # A running row on its first delivery may still belong to an
                # active consumer. Only redelivery proves its visibility lease
                # expired and makes recovery safe.
                return DebateWorkerResult(
                    outcome="deferred_running",
                    queue_message_id=queue_message_id,
                    job_id=job.id,
                    read_count=claimed.read_count,
                )
            if session.status in {"cancel_requested", "interrupted_awaiting_user"}:
                cancelled_job = cancel_job(
                    job,
                    at=max(job.updated_at, session.updated_at),
                )
                await asyncio.to_thread(
                    self.repository.update_job,
                    cancelled_job,
                    expected_status="running",
                )
                if session.status == "cancel_requested":
                    await asyncio.to_thread(
                        self.orchestrator.request_cancellation,
                        session.id,
                        session.user_id,
                        session.active_generation_id,
                    )
                await self._archive(queue_message_id)
                return DebateWorkerResult(
                    outcome="cancelled",
                    queue_message_id=queue_message_id,
                    job_id=job.id,
                    read_count=claimed.read_count,
                )
            if job.attempt_count >= job.max_attempts:
                await self._fail_exhausted(job.id, job.attempt_count)
                await self._archive(queue_message_id)
                return DebateWorkerResult(
                    outcome="failed",
                    queue_message_id=queue_message_id,
                    job_id=job.id,
                    read_count=claimed.read_count,
                )
            _, job = await asyncio.to_thread(
                self.queue.requeue_running_job,
                job.id,
                expected_attempt_count=job.attempt_count,
            )

        try:
            finished_session = await self.orchestrator.execute_job_streaming(job.id)
        except DebateRetryableOrchestrationError as exc:
            current_job = await asyncio.to_thread(self.repository.get_job, job.id)
            if current_job is None or current_job.status != "running":
                raise DebateRepositoryError(
                    "Retryable Debate execution did not retain a running Job"
                )
            if current_job.attempt_count >= current_job.max_attempts:
                await self._fail_exhausted(current_job.id, current_job.attempt_count)
                await self._archive(queue_message_id)
                return DebateWorkerResult(
                    outcome="failed",
                    queue_message_id=queue_message_id,
                    job_id=current_job.id,
                    read_count=claimed.read_count,
                )
            retried_session, retried_job = await asyncio.to_thread(
                self.queue.requeue_running_job,
                current_job.id,
                expected_attempt_count=current_job.attempt_count,
                provider_request_count=exc.provider_request_count,
                prompt_tokens=exc.prompt_tokens,
                completion_tokens=exc.completion_tokens,
            )
            retry_delay_seconds = self._retry_delay_seconds(
                current_job.attempt_count,
                exc.retry_after_seconds,
            )
            retried = await asyncio.to_thread(
                self.queue.retry_job_message,
                queue_message_id,
                delay_seconds=retry_delay_seconds,
            )
            if not retried:
                raise DebateRepositoryError(
                    "Worker could not reschedule its Queue message"
                )
            self.orchestrator.publish_retry_scheduled(
                retried_session,
                retried_job,
                retry_delay_seconds=retry_delay_seconds,
            )
            return DebateWorkerResult(
                outcome="retry_scheduled",
                queue_message_id=queue_message_id,
                job_id=current_job.id,
                read_count=claimed.read_count,
                retry_delay_seconds=retry_delay_seconds,
            )
        except DebateOrchestrationError:
            current_job = await asyncio.to_thread(self.repository.get_job, job.id)
            if current_job is not None and current_job.status == "failed":
                await self._archive(queue_message_id)
                return DebateWorkerResult(
                    outcome="failed",
                    queue_message_id=queue_message_id,
                    job_id=job.id,
                    read_count=claimed.read_count,
                )
            raise

        current_job = await asyncio.to_thread(self.repository.get_job, job.id)
        if current_job is None or current_job.status not in {
            "completed",
            "cancelled",
            "failed",
        }:
            raise DebateRepositoryError("Worker stage did not reach a durable terminal Job state")
        await self._archive(queue_message_id)
        outcome: DebateWorkerOutcome = (
            "cancelled" if current_job.status == "cancelled" else "completed"
        )
        return DebateWorkerResult(
            outcome=outcome,
            queue_message_id=queue_message_id,
            job_id=job.id,
            read_count=claimed.read_count,
        )

    async def run_until_idle(self, *, max_messages: int = 10) -> list[DebateWorkerResult]:
        if not 1 <= max_messages <= 100:
            raise ValueError("Worker batch size is outside safe bounds")
        results: list[DebateWorkerResult] = []
        for _ in range(max_messages):
            result = await self.run_once()
            results.append(result)
            if result.outcome == "idle":
                break
        return results

    async def run_forever(
        self,
        stop_event: asyncio.Event,
        *,
        poll_seconds: float = 1.0,
    ) -> None:
        if not 0.1 <= poll_seconds <= 10:
            raise ValueError("Worker poll interval is outside safe bounds")
        while not stop_event.is_set():
            try:
                result = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # The Queue message stays unarchived. Its visibility timeout is
                # the durable recovery path if this process or dependency fails.
                # Log only the exception type: provider/database error text can
                # contain upstream payloads that do not belong in application logs.
                logger.warning(
                    "Debate Worker tick failed safely (%s)",
                    type(exc).__name__,
                )
                result = DebateWorkerResult(outcome="idle")
            if result.outcome not in {"idle", "deferred_running"}:
                continue
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except TimeoutError:
                pass

    async def _archive(self, queue_message_id: int) -> None:
        archived = await asyncio.to_thread(
            self.queue.archive_job_message,
            queue_message_id,
        )
        if not archived:
            raise DebateRepositoryError("Worker could not archive its Queue message")

    async def _fail_exhausted(self, job_id: UUID, attempt_count: int) -> None:
        session, job = await asyncio.to_thread(
            self.queue.fail_exhausted_job,
            job_id,
            expected_attempt_count=attempt_count,
        )
        self.orchestrator.publish_retry_exhausted(session, job)

    @staticmethod
    def _retry_delay_seconds(
        attempt_count: int,
        retry_after_seconds: int | None,
    ) -> int:
        exponential_backoff = min(2**attempt_count, 60)
        return max(exponential_backoff, retry_after_seconds or 0)
