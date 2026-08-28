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
from app.services.debate_orchestrator import DebateOrchestrationError, DebateOrchestrator


logger = logging.getLogger(__name__)


DebateWorkerOutcome = Literal[
    "idle",
    "completed",
    "cancelled",
    "failed",
    "skipped_terminal",
    "deferred_running",
    "invalid",
]


@dataclass(frozen=True)
class DebateWorkerResult:
    outcome: DebateWorkerOutcome
    queue_message_id: int | None = None
    job_id: UUID | None = None
    read_count: int = 0


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
            await self._archive(queue_message_id)
            return DebateWorkerResult(
                outcome="skipped_terminal",
                queue_message_id=queue_message_id,
                job_id=job.id,
                read_count=claimed.read_count,
            )
        if job.status == "running":
            # A prior process may have stopped after claiming. Leave the message
            # unarchived so the recovery policy can inspect it on redelivery.
            return DebateWorkerResult(
                outcome="deferred_running",
                queue_message_id=queue_message_id,
                job_id=job.id,
                read_count=claimed.read_count,
            )

        try:
            finished_session = await self.orchestrator.execute_job_streaming(job.id)
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
            "cancelled" if finished_session.status == "cancelled" else "completed"
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
